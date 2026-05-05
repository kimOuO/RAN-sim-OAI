# RANsim-CU

5G NR Centralized Unit (CU-CP + CU-UP) simulator, Django-based, behavioural
fidelity to OpenAirInterface5G (`/home/mitlab/openairinterface5g/`). All
inter-system traffic is HTTP POST + JSON; protocol semantics (F1AP, NGAP,
E1AP, PDCP, SDAP, GTP-U) are mirrored at the procedural level rather than at
the wire level.

Part of the RANsim platform — peer repos: `RANsim-DU`, `RANsim-RU`,
`RANsim-Physics`. Shared message types live in
[`ran-sim-protocol`](../Physics_sim/ran-sim-protocol).

---

## Quick start

```bash
cd /home/mitlab/XAPP_DT/RANsim-CU
cp .env.sample .env
pip install -r requirements/local.txt
pip install /home/mitlab/XAPP_DT/Physics_sim/ran-sim-protocol
bash shell/init_project.sh
python manage.py runserver 0.0.0.0:8000
```

## Docker

```bash
# pre-create the platform-wide bridge if absent
docker network create ransim-net 2>/dev/null || true
docker compose up --build cu
# CU is reachable on :8101
```

The `ran-sim-protocol` package is mounted at `/tmp/ran-sim-protocol` and
installed by `shell/entrypoint.sh` on container start.

---

## Endpoints (all POST)

URL pattern: `/api/v0.1/CU/<Module>/<Component>/<Element>`

### CU-CP — F1AP (DU → CU)
| Endpoint | Body |
|---|---|
| `F1AP/F1ApRouter/du_setup` | `F1Setup` |
| `F1AP/F1ApRouter/ul_rrc_message` | `UlRrcMessageTransfer` |
| `F1AP/F1ApRouter/measurement_report` | `GnbDuMeasurementReport` |

### CU-CP — NGAP (5GC → CU)
| Endpoint | Body |
|---|---|
| `NGAP/NgapRouter/initial_ue_message` | `InitialUeMessage` (echo) |
| `NGAP/NgapRouter/initial_context_setup` | `InitialContextSetupRequest` |
| `NGAP/NgapRouter/downlink_nas_transport` | `DownlinkNasTransport` |

### CU-CP — Dashboard
| Endpoint | Body |
|---|---|
| `Session/SessionController/list` | `{}` |
| `Session/SessionController/get_state` | `{ue_id}` |
| `Session/SessionController/handover` | `{ue_id, target_cell}` |

### CU-CP — E2 KPM
| Endpoint | Body |
|---|---|
| `E2/E2KpmReporter/read` | `{}` |

### CU-UP — E1AP (CU-CP → CU-UP)
| Endpoint | Body |
|---|---|
| `E1AP/E1ApRouter/bearer_context_setup` | `BearerContextSetupRequest` |

### CU-UP — Observability
| Endpoint | Body |
|---|---|
| `UP/Drb/list` | `{}` |
| `UP/Drb/read` | `{ue_id, drb_id}` |

---

## Curl recipes

### 1) DU starts, sends F1 Setup
```bash
curl -X POST http://localhost:8000/api/v0.1/CU/F1AP/F1ApRouter/du_setup \
  -H 'Content-Type: application/json' \
  -d '{
    "gnb_du_id": 1,
    "served_cells": [
      {"cell_id":"c1","pci":1,"frequency_ghz":3.5,"bandwidth_mhz":100,"served_plmn":"00101"}
    ]
  }'
```

### 2) UE attach (UL RRC: Setup Request → Setup Complete)
```bash
SETUP_REQ=$(python -c '
import base64, json
print(base64.b64encode(json.dumps({"type":"RRCSetupRequest","payload":{}}).encode()).decode())
')
curl -X POST http://localhost:8000/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message \
  -H 'Content-Type: application/json' \
  -d "{\"ue_id\":\"ue-001\",\"rrc_msg_b64\":\"${SETUP_REQ}\"}"

SETUP_COMPLETE=$(python -c '
import base64, json
print(base64.b64encode(json.dumps({"type":"RRCSetupComplete","payload":{"nas_pdu_b64":""}}).encode()).decode())
')
curl -X POST http://localhost:8000/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message \
  -H 'Content-Type: application/json' \
  -d "{\"ue_id\":\"ue-001\",\"rrc_msg_b64\":\"${SETUP_COMPLETE}\"}"
```

### 3) Mock 5GC pushes Initial Context Setup
```bash
curl -X POST http://localhost:8000/api/v0.1/CU/NGAP/NgapRouter/initial_context_setup \
  -H 'Content-Type: application/json' \
  -d '{
    "ran_ue_ngap_id": 12345,
    "amf_ue_ngap_id": 99999,
    "pdu_session_resources": [
      {"pdu_session_id": 1, "qos_flow_5qi":[9], "s_nssai":"01:000000"}
    ]
  }'
```

### 4) DU reports periodic measurement
```bash
curl -X POST http://localhost:8000/api/v0.1/CU/F1AP/F1ApRouter/measurement_report \
  -H 'Content-Type: application/json' \
  -d '{
    "ue_id":"ue-001",
    "rsrp_dbm": -90.0, "sinr_db": 5.0,
    "throughput_dl_mbps": 50.0,
    "neighbor_cells": [{"cell_id":"c2","rsrp_dbm":-80.0,"rsrq_db":-10.0}]
  }'
```
Two such calls > TTT apart will trigger an A3 handover.

### 5) Dashboard queries
```bash
curl -X POST http://localhost:8000/api/v0.1/CU/Session/SessionController/list -d '{}'
curl -X POST http://localhost:8000/api/v0.1/CU/E2/E2KpmReporter/read -d '{}'
```

---

## Architecture (mapping to OAI)

| Component | OAI ref | This repo |
|---|---|---|
| RRC task switch | `openair2/RRC/NR/rrc_gNB.c:3030` | `cu_cp.actors.f1ap_router_actor` + `services/optional/rrc/state_machine.py` |
| F1AP CU dispatch | `openair2/F1AP/f1ap_cu_task.c:110` | `cu_cp.actors.f1ap_router_actor` |
| NGAP handlers | `openair3/NGAP/ngap_gNB_handlers.c` | `cu_cp.actors.ngap_router_actor` + `services/optional/ngap/ngap_handler.py` |
| E1 abstraction | `openair2/RRC/NR/cucp_cuup_if.h` | `cu_cp.services.business.cuup_client_operations` (direct vs HTTP) |
| Bearer Ctx Setup | `openair2/LAYER2/nr_pdcp/cucp_cuup_handler.c:162` | `cu_up.services.optional.e1ap.e1ap_handler` |
| PDCP | `openair2/LAYER2/nr_pdcp/nr_pdcp_entity.c` | `cu_up.services.optional.pdcp.pdcp_entity` |
| SDAP | `openair2/SDAP/nr_sdap/nr_sdap_entity.c` | `cu_up.services.optional.sdap.sdap_entity` |
| GTP-U | `openair3/ocp-gtpu/gtp_itf.cpp` | `cu_up.services.optional.gtpu.gtpu_tunnel` |
| A3 + TTT | `TS 38.331 §5.5.4.4` | `cu_cp.services.optional.mobility.a3_handover_calculation` |

### Integrated vs split CU mode

Mirrors OAI's `cucp_cuup_if_t` (`openair2/RRC/NR/cucp_cuup_direct.c` vs
`cucp_cuup_e1ap.c`):

- **Integrated** (`HTTP_CUUP_HOST` empty) — `CuupClientBusinessService` calls
  `E1apHandler.bearer_context_setup` in-process. Same code path is exercised
  by `cu_up.actors.E1ApRouterActor`.
- **Split** (`HTTP_CUUP_HOST` set) — request is POSTed to a separate CU-UP
  container at `E1AP/E1ApRouter/bearer_context_setup`.

---

## Tests

```bash
pip install -r requirements/test.txt
pytest
```

Covered:
- `cu_cp/tests/services/test_rrc_state_machine.py` — FSM transitions
- `cu_cp/tests/services/test_a3_handover.py` — TTT timing
- `cu_cp/tests/unit_test/test_du_setup.py` — F1 Setup persistence
- `cu_cp/tests/unit_test/test_ul_rrc_message.py` — IDLE → SETUP → CONNECTED
- `cu_up/tests/services/test_pdcp_sequence.py` — SN monotonic + wrap
- `cu_up/tests/unit_test/test_e1ap_bearer.py` — Bearer Setup + DRB persisted

---

## Out of scope (per LLM_CU prompt §10)
- Real ASN.1 wire format (we use base64 JSON containers)
- Real SCTP / eCPRI (HTTP throughout)
- Real AES ciphering / integrity protection (PDCP entity is stateful but no crypto)
- Real 5GC AMF / UPF (mock endpoint only)
