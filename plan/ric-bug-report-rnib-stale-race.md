# OSC Near-RT RIC Bug Report — R-NIB Stale Race after RAN Reconnect

**Symptom**: RAN-side e2term SCTP connection breaks ~5 minutes after every successful E2 Setup, with no application-layer error from RAN.

**Affected**: OSC RIC m-release (likely also l-release; n-release possibly fixed via rewrite).

**Severity**: Functional — no xApp can receive `RIC_INDICATION` because association expires before xApp subscription propagates.

---

## 1. Observed Symptom (from RAN side)

```
TIMING:
  T=0      RAN sends SCTP INIT to e2term:36422 → ESTABLISHED
  T+1ms    RAN sends E2 Setup Request (APER, ranName=gnb_xxx, RANfunction id=2 KPM)
  T+5ms    RIC e2term replies E2 Setup Response (RANfunctionsAccepted: id=2)
  T+5ms    RAN E2 Setup state = SUCCESS, marks SCTP healthy
  
  T+5min   RAN socket recv() returns 0 bytes (peer half-close)
           No prior SHUTDOWN_REQ from app layer
           No xApp had successfully subscribed during this 5 min window
```

**Counter evidence over 25 hour run**:
```
sctp_link.connected      = true              (current SCTP state)
e2_setup.completed       = true              (E2 Setup OK each cycle)
pdu_sent_count           = 27,262            (RIC_INDICATION sent)
pdu_recv_count           = 2                 (only E2 Setup Resp + 1 other?)
last_disconnect_at_ms    = 1778134547034
last_connect_at_ms       = 1778134847035     (delta = 300s exactly)
```

**Observation**: The 300s = 5 min disconnect interval is deterministic. Every reconnect cycle gets exactly 5 minutes of valid connection, then `recv 0 bytes`.

---

## 2. Hypothesised Root Cause in RIC (OSC e2mgr)

The pattern matches `RanReconnectionManager` in `ric-plt/e2mgr` taking the **`dissociate-fail` path** when handling reconnection of a previously-known RAN node.

### Suspected path

```
e2mgr/managers/ran_reconnection_manager.go (similar location, m-release)

func (h *RanReconnectionManager) ReconnectRan(inventoryName string) error {
    nodebInfo, _ := h.rNibDataService.GetNodeb(inventoryName)
    
    if nodebInfo.ConnectionStatus == DISCONNECTED 
       && nodebInfo.AssociatedE2tInstanceAddress == "" {
        //                                       ↑↑↑
        // Empty associated address triggers fail path:
        //   tries to dissociate from a non-existent E2T instance
        //   → DissociateRanFromE2t error
        //   → R-NIB updated with status=STALE_DURING_RECONNECT
        //   → marks NodebInfo for cleanup
    }
    ...
}
```

The `AssociatedE2tInstanceAddress` field is empty on **fresh adapter restart** (because pod was killed before clean shutdown wrote the address) or after our adapter's previous SCTP socket close.

### Cleanup task

```
e2mgr/managers/stale_connection_manager.go (or rmr_message_handler.go)

Periodic task (default 300s interval) walks R-NIB looking for:
  - status == DISCONNECTED with stale timestamp
  - status == STALE_DURING_RECONNECT
  
  Action: send SCTP SHUTDOWN to associated socket and remove from R-NIB.
```

The 300s default in `RIC_E2MGR_STALE_CONNECTION_TIMEOUT_SEC` (or similar) explains the deterministic 5-minute interval observed from RAN side.

---

## 3. Reproduction

Minimal repro (no xApp needed):

1. Deploy OSC RIC m-release (e2mgr + e2term + Redis SDL)
2. From any host, open SCTP connection to `<e2term>:36422`
3. Send any well-formed E2 Setup Request (ranName=test_ran)
4. Verify successful E2 Setup Response received
5. Keep connection idle (no further PDUs from RAN, no xApp subscribes)
6. **Observe**: socket gets SHUTDOWN at exactly ~300s

If you tcpdump on RIC side, you should see:
- T=0:   `INIT, INIT_ACK, COOKIE_ECHO, COOKIE_ACK` (4-way handshake)
- T+5s:  E2 Setup PDU exchange
- T+300s: `SHUTDOWN, SHUTDOWN_ACK, SHUTDOWN_COMPLETE` initiated by RIC e2term

Compare `kubectl logs -n ricplt deployment-ricplt-e2mgr` around T+295s onwards for entries like:
- `"stale connection detected"` 
- `"dissociating ran from e2t"`
- `"failed to dissociate ran"` (the bug)

---

## 4. Expected vs Actual Behaviour

### Expected (per O-RAN.WG3.E2GAP spec)

After E2 Setup success:
- E2 connection MUST persist until either side initiates `RICserviceUpdate` or one side fails
- RIC SHOULD NOT spontaneously disassociate a CONNECTED RAN unless:
  - Explicit operator action
  - SCTP heartbeat failure (T1 timer expired)
  - Operational impairment (e2t instance restart)

### Actual

RIC e2mgr's `RanReconnectionManager` mis-handles the case where:
- `ConnectionStatus = CONNECTED` (just set by E2 Setup success)
- `AssociatedE2tInstanceAddress = ""` (not yet written by association handler, race condition)

The reconciliation logic interprets `(CONNECTED, "")` as "needs reconnect" instead of "newly connected", and triggers dissociate-fail path.

---

## 5. Proposed Fix Direction (for RIC team)

### Option A — Race-condition fix (minimal diff)

Make E2 Setup success handler **atomic** with respect to `AssociatedE2tInstanceAddress` write:

```go
// e2mgr/managers/e2_setup_request_handler.go (pseudo-code)

func (h *E2SetupRequestNotificationHandler) Handle(...) {
    // ...existing E2 Setup processing...
    
    // ATOMIC: status + associated address must be written together
    nodebInfo.ConnectionStatus = CONNECTED
    nodebInfo.AssociatedE2tInstanceAddress = e2tInstanceAddress  // ← must NOT be ""
    rNibDataService.UpdateNodebInfo(nodebInfo)  // single transaction
}
```

### Option B — Reconnection logic fix

Make `RanReconnectionManager.ReconnectRan` tolerate empty `AssociatedE2tInstanceAddress`:

```go
if nodebInfo.AssociatedE2tInstanceAddress == "" {
    // No previous association — this is a fresh connect, not a reconnect
    log.Infof("ran %s has no associated E2T — treating as fresh connect", inventoryName)
    return nil   // do NOT trigger dissociate path
}
```

### Option C — Backport from later release

If `n-release` or `o-release` rewrote this logic correctly, backport the relevant commit to `m-release` branch.

### Option D — Disable stale cleanup for connected RANs

In `stale_connection_manager.go`, only mark stale if:
- status == DISCONNECTED for > timeout, OR
- last heartbeat > timeout (use SCTP keepalive timestamp)

Do NOT mark stale based on R-NIB metadata alone if SCTP socket is alive.

---

## 6. Workarounds the RAN side has implemented

For reference, these are RAN-side mitigations we use today:

1. **Long backoff before reconnect**: 300s `_BACKOFF_AFTER_SUCCESS` to avoid hammering RIC during cleanup window
2. **Don't trust own subscription state**: indication producers only start when RIC sends fresh `RIC_SUB_REQ`, not from RAN-side memory of past subscriptions
3. **Distinguish recv timeout vs peer-close**: avoid busy-spin when RIC half-closes socket

These mitigations make RAN survivable but **xApp still cannot receive any `RIC_INDICATION`** because:
- xApp subscribes via RIC submgr
- submgr forwards `RIC_SUB_REQ` to e2term → routes to e2adapter
- e2adapter starts producer, sends `RIC_INDICATION`
- 5 min later: SCTP shutdown → producer dies before xApp gets meaningful data
- xApp re-subscribes after reconnect → another 5 min cycle

The RAN-side fixes don't solve the user-facing problem; only RIC-side fix can.

---

## 7. RIC Components to Inspect

| Component | Repo | Likely File | What to Check |
|:---|:---|:---|:---|
| e2mgr | `ric-plt/e2mgr` | `managers/ran_reconnection_manager.go` | dissociate path conditions |
| e2mgr | same | `managers/e2_setup_request_handler.go` | atomicity of NodebInfo update |
| e2mgr | same | `managers/stale_connection_manager.go` | stale criteria |
| e2mgr config | helm chart values | `RIC_E2MGR_*` env vars | `STALE_CONNECTION_TIMEOUT_SEC` |
| R-NIB schema | `ric-plt/nodeb-rnib` | `entities/nodeb_info.proto` | NodebInfo state machine |

---

## 8. Logs to capture for RIC team

If the RIC team wants concrete logs from our side:

```bash
# RAN-side adapter snapshot (any time during run)
curl -s http://<adapter>:8201/api/v0.1/E2Adapter/Status/read | jq .

# RAN-side packet capture (first 10 min after fresh restart)
sudo tcpdump -i <interface> -w /tmp/e2-trace.pcap \
  'sctp port 36422'   # capture for 600 seconds

# RIC-side logs to correlate
kubectl logs -n ricplt deployment-ricplt-e2mgr --tail=2000 > e2mgr.log
kubectl logs -n ricplt statefulset-ricplt-e2term-alpha --tail=2000 > e2term.log
kubectl logs -n ricplt deployment-ricplt-rtmgr --tail=2000 > rtmgr.log

# R-NIB snapshot
kubectl exec -n ricplt <dbaas-pod> -- redis-cli KEYS '*' | head -50
kubectl exec -n ricplt <dbaas-pod> -- redis-cli HGETALL "{namespace},gnb_xxx"
```

---

## 9. Severity Justification

This bug effectively prevents **any** RIC + e2adapter combination from delivering `RIC_INDICATION` to xApp in steady state. Without this fixed, the entire E2 → xApp pipeline is broken regardless of what either RAN or xApp does.

The 5-minute SCTP cycling also generates ~50 GB/day of e2adapter logs (RAN-side), but that's a side effect.
