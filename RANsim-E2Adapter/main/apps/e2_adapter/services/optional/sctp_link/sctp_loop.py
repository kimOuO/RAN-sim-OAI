"""SCTP background loop — long-running daemon thread driving E2AP plane.

P2.8.1: 開 SCTP socket、編 E2 Setup Request、送出、等 E2 Setup Response。
P2.8.2+: Subscribe / Indication / Control 流程。

env:
  E2_ADAPTER_LINK_ENABLED   — '1' to start loop (default '0' so unit tests don't connect)
  RIC_E2TERM_HOST           — RIC e2term host (e.g. 10.3.0.71)
  RIC_E2TERM_PORT           — RIC e2term SCTP port (32222)

SCTP 細節：
  - PPID = 70 (E2AP per O-RAN convention)
  - APER encoding (Aligned Packed Encoding Rules)
  - Stream 0 for unsolicited messages
"""
from __future__ import annotations

import socket
import threading
import time

from main.apps.e2_adapter.services.optional.event_log import ring as event_ring
from main.apps.e2_adapter.services.optional.event_log import kpm_snapshot
from main.utils.env_loader import get_bool, get_int, get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)


_E2AP_SCTP_PPID = 70    # O-RAN E2AP payload protocol identifier
_RECV_BUF = 65535
_CONNECT_TIMEOUT_SEC = 8.0
_RECV_TIMEOUT_SEC = 30.0  # E2 Setup Response 必須 30 秒內回，否則重連


_started_flag = threading.Event()
_thread: threading.Thread | None = None

# Per-subscription indication producer state
# key: adapter-side ric_req_id signature → {sub_id, period_ms, ran_func_id, action_ids, sn, thread, stop}
_ACTIVE_SUBS: dict[str, dict] = {}
_SUBS_LOCK = threading.Lock()
_SCTP_SOCK_LOCK = threading.Lock()  # 多 indication thread 共用同 SCTP socket，要 serialize send

# Y1: E2 Reset debounce — sim CU 重啟後多個 producer 會同時抓到 SubNotFoundError,
# 只該送一次 Reset 給 RIC, 不然 RIC 那邊會看到一連串 Reset 浪費 transactionID.
_LAST_RESET_SENT_MS = 0
_RESET_COOLDOWN_MS = 30000  # 30s — RIC 通常 5s 內就會重發 SUB_REQ, 30s 夠
_RESET_LOCK = threading.Lock()


def link_target() -> tuple[str, int]:
    """Return (host, port) of the configured RIC e2term."""
    host = get_str("RIC_E2TERM_HOST", "")
    port = get_int("RIC_E2TERM_PORT", 32222)
    return host, port


def is_enabled() -> bool:
    return get_bool("E2_ADAPTER_LINK_ENABLED", default=False)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _open_sctp_socket() -> socket.socket | None:
    """Create SCTP one-to-one socket (SOCK_STREAM, IPPROTO_SCTP).

    SCTP multi-homing self-ABORT 修復 — bind 到指定 IP（不是 0.0.0.0）：
    多 IP host (sim 有 enp1s0 + docker0 + 多個 br-*) 用 0.0.0.0 會自動把
    所有 IP 都當 secondary path 廣告給 peer，peer 對 docker0 IP (172.17.0.1)
    送 HEARTBEAT，遇到 RIC 那台也有 172.17.0.1 → 走 lo 回到 RIC 自己 SCTP
    stack → 自動回 ABORT 殺整個 association。

    bind 到 enp1s0 IP (10.3.0.217) 從源頭只廣告一個 path。
    env: SCTP_BIND_IP — 預設 0.0.0.0 (auto)，多 IP host 必須設成 enp1s0 IP。
    """
    try:
        import sctp  # type: ignore
        sock = sctp.sctpsocket_tcp(socket.AF_INET)
        bind_ip = get_str("SCTP_BIND_IP", "0.0.0.0")
        if bind_ip and bind_ip != "0.0.0.0":
            try:
                sock.bind((bind_ip, 0))
                logger.info("SCTP socket bound to %s (single-homed)", bind_ip)
            except Exception as bind_exc:
                logger.warning("SCTP bind to %s failed: %s — fall back to 0.0.0.0",
                               bind_ip, bind_exc)
        sock.settimeout(_CONNECT_TIMEOUT_SEC)
        return sock
    except Exception as exc:
        logger.error("failed to create SCTP socket: %s", exc)
        return None


def _send_sctp(sock, data: bytes, ppid: int = _E2AP_SCTP_PPID) -> bool:
    """SCTP send on stream 0 with E2AP PPID.

    pysctp 0.7.2 在 _sctp.c 裡有自動 htonl（看 sctp_sendmsg call），所以這裡傳
    host order 70 即可。E2AP 標準 PPID = 70 per O-RAN.

    多 indication thread 共用一個 socket，這裡 lock serialize send。
    """
    try:
        with _SCTP_SOCK_LOCK:
            sock.sctp_send(msg=data, ppid=ppid, stream=0)
        return True
    except Exception as exc:
        logger.error("SCTP send failed: %s", exc)
        return False


class _PeerClosedError(Exception):
    """Peer half-closed the SCTP socket (recv 0 bytes). 必須 break 出 inner loop 重連,
    不能繼續 spin call recv() 否則每次都拿 0 bytes 打 100+ warning/sec 把 log 撐爆 (45GB/天)。"""


def _recv_sctp(sock) -> bytes | None:
    """Receive one SCTP message.

    回傳語意:
        bytes (non-empty)        → 收到一個 PDU
        None                     → select timeout, 沒資料但 socket 還活, 可繼續 loop
        raises _PeerClosedError  → recv 0 bytes, peer 半死, 必須跳出 inner loop 重連

    pysctp.sctp_recv 不尊重 settimeout，改用 plain recv() + select。
    """
    import select
    try:
        ready, _, _ = select.select([sock], [], [], _RECV_TIMEOUT_SEC)
        if not ready:
            logger.debug("SCTP recv timed out after %ds (no data)", _RECV_TIMEOUT_SEC)
            return None
        data = sock.recv(_RECV_BUF)
        if not data:
            # peer half-close — caller MUST break inner loop, 不可 continue
            raise _PeerClosedError("SCTP peer closed connection (recv 0 bytes)")
        return data
    except socket.timeout:
        # 理論上不會走這裡 (我們用 select), 但保險: 視為 timeout
        logger.debug("SCTP recv socket.timeout")
        return None
    except _PeerClosedError:
        raise
    except Exception as exc:
        # 未知錯誤 — 視為連線壞掉,促 outer reconnect
        logger.error("SCTP recv failed: %s", exc)
        raise _PeerClosedError(f"recv error: {exc!r}")


def _do_e2_setup(sock) -> bool:
    """Fetch globalE2node-ID from sim CU, encode E2 Setup Request, send, wait response."""
    from main.apps.e2_adapter.models.connection_state import get_registry
    from main.apps.e2_adapter.services.business.memory_state_operations import (
        MemoryStateBusinessService,
    )
    from main.apps.e2_adapter.services.optional.codec import e2ap_codec
    from main.apps.e2_adapter.services.optional.sim_bridge import sim_http_client

    registry = get_registry()

    # Step 1: pull from sim
    node_id = sim_http_client.fetch_e2_node_id()
    if node_id is None:
        MemoryStateBusinessService.update_state(
            registry, last_error="sim CU /E2NodeId/read failed"
        )
        return False

    # Step 2: encode
    try:
        request_bytes = e2ap_codec.encode_e2_setup_request(node_id)
    except Exception as exc:
        logger.exception("encode_e2_setup_request failed")
        MemoryStateBusinessService.update_state(
            registry, last_error=f"encode failed: {exc!r}"
        )
        return False
    logger.info(
        "E2 Setup Request encoded — %d bytes APER (ranName=%s)",
        len(request_bytes), node_id.get("expected_ran_name", ""),
    )

    # Step 3: SCTP send
    if not _send_sctp(sock, request_bytes):
        MemoryStateBusinessService.update_state(
            registry, last_error="SCTP send E2 Setup Request failed"
        )
        return False
    MemoryStateBusinessService.update_state(
        registry, pdu_sent_count=registry.get_connection().pdu_sent_count + 1,
    )

    # Step 4: wait response
    response_bytes = _recv_sctp(sock)
    if response_bytes is None:
        MemoryStateBusinessService.update_state(
            registry, last_error="no E2 Setup Response (timeout)"
        )
        return False

    MemoryStateBusinessService.update_state(
        registry, pdu_recv_count=registry.get_connection().pdu_recv_count + 1,
    )

    # Step 5: decode + extract acceptedRANfunctions
    try:
        decoded = e2ap_codec.decode_e2ap_pdu(response_bytes)
    except Exception as exc:
        logger.exception("decode E2 Setup Response failed")
        MemoryStateBusinessService.update_state(
            registry, last_error=f"decode failed: {exc!r}"
        )
        return False

    accepted_ids: list[int] = []
    rejected_ids: list[int] = []
    fail_reason = ""
    try:
        outcome_choice, outcome_msg = decoded
        if outcome_choice == "successfulOutcome":
            inner = outcome_msg["value"]
            if inner[0] == "E2setupResponse":
                for ie in inner[1].get("protocolIEs", []):
                    if ie["id"] == 9:    # RANfunctionsAccepted-List
                        for rf_ie in ie["value"][1]:
                            accepted_ids.append(rf_ie["value"][1]["ranFunctionID"])
                    elif ie["id"] == 13:  # RANfunctionsRejected-List
                        for rf_ie in ie["value"][1]:
                            rejected_ids.append(rf_ie["value"][1]["ranFunctionID"])
        elif outcome_choice == "unsuccessfulOutcome":
            # E2setupFailure: IE id=1 Cause, id=2 CriticalityDiagnostics
            inner = outcome_msg["value"]
            if inner[0] == "E2setupFailure":
                for ie in inner[1].get("protocolIEs", []):
                    if ie["id"] == 1:    # Cause
                        cause_choice, cause_val = ie["value"][1]
                        fail_reason = f"cause.{cause_choice}={cause_val!r}"
                    elif ie["id"] == 2:  # CriticalityDiagnostics
                        diag = ie["value"][1]
                        proc = diag.get("procedureCode")
                        ies = diag.get("iEsCriticalityDiagnostics", [])
                        ie_details = [(d.get("iECriticality"), d.get("iE_ID"), d.get("typeOfError"))
                                      for d in ies]
                        fail_reason += f" diag.proc={proc} ies={ie_details}"
            logger.warning("E2 Setup REJECTED: %s", fail_reason)
        else:
            logger.warning("E2 Setup outcome was %s (not successful)", outcome_choice)
    except Exception as exc:
        logger.exception("parse E2 Setup Response IEs failed")

    is_success = (outcome_choice == "successfulOutcome")
    MemoryStateBusinessService.update_state(
        registry,
        e2_setup_completed=is_success,
        accepted_ran_function_ids=accepted_ids,
        rejected_ran_function_ids=rejected_ids,
        last_error=fail_reason,
    )
    logger.info(
        "E2 Setup outcome=%s accepted=%s rejected=%s reason=%s",
        outcome_choice, accepted_ids, rejected_ids, fail_reason or "(success)",
    )
    event_ring.record_e2_setup_outcome(outcome_choice, accepted_ids, rejected_ids, fail_reason)
    return is_success


def _link_loop(host: str, port: int) -> None:
    """Daemon thread main loop — connect → E2 setup → recv loop → reconnect on fail."""
    from main.apps.e2_adapter.models.connection_state import get_registry
    from main.apps.e2_adapter.services.business.memory_state_operations import (
        MemoryStateBusinessService,
    )

    registry = get_registry()
    # OSC RIC m-release 已知 bug：RanReconnectionManager 對「stale RAN +
    # associatedE2tInstance=空」走 dissociate-fail 路徑。每次重連都會把 R-NIB
    # 寫成 stale，跟對方清 R-NIB 速度競爭。
    # 對策：兩種 backoff 都用長值（env 可調，default 5 分鐘）。希望立刻重連請
    # docker restart ransim-e2adapter。
    _BACKOFF_FRESH = get_int("SCTP_BACKOFF_INITIAL_SEC", default=300)
    _BACKOFF_AFTER_SUCCESS = get_int("SCTP_BACKOFF_AFTER_SUCCESS_SEC", default=300)
    had_success = False

    while True:
        backoff_sec = _BACKOFF_AFTER_SUCCESS if had_success else _BACKOFF_FRESH
        sock = _open_sctp_socket()
        if sock is None:
            logger.info("SCTP socket failed — sleep %ds before retry", backoff_sec)
            time.sleep(backoff_sec)
            continue

        try:
            logger.info("SCTP connecting to %s:%d ...", host, port)
            sock.connect((host, port))
            MemoryStateBusinessService.update_state(
                registry,
                sctp_connected=True,
                last_connect_at_ms=_now_ms(),
                last_error="",
            )
            logger.info("SCTP connected")
            event_ring.record_sctp_connect(host, port)

            # Step: send E2 Setup Request, wait response
            if _do_e2_setup(sock):
                had_success = True
                # NOTE (2026-05-08 fix): 不再從 sim CU 重建 indication producer.
                # 之前的 _restore_producers_from_sim() 用 sim CU 自己的 subscription
                # list 重啟 producer thread, 但那個 sub_id 只有 sim CU 跟 adapter 認得
                # → RIC 跟 xApp 不認得 → 27262 個 indication 全被 RIC silent drop.
                # 正確: producer 只應在收 RIC_SUB_REQ 時啟動 (見 _dispatch_pdu).
                # Step: recv loop with PDU dispatcher
                # 修 (2026-05-08): _recv_sctp 對 peer-closed 改 raise _PeerClosedError,
                # 不再讓 inner loop spin call recv() 拿 0 bytes 噴 100+ warning/sec.
                while True:
                    try:
                        pdu = _recv_sctp(sock)
                    except _PeerClosedError as exc:
                        logger.warning(
                            "SCTP peer half-closed: %s — break to outer reconnect", exc,
                        )
                        break
                    if pdu is None:
                        # timeout — keep alive, no data this round
                        continue
                    MemoryStateBusinessService.update_state(
                        registry,
                        pdu_recv_count=registry.get_connection().pdu_recv_count + 1,
                    )
                    # 修 (2026-05-10): handler exception 不應拖垮 SCTP association.
                    # 任何單一 PDU 處理失敗 → log full traceback, 繼續 listen 下一筆.
                    # spec 上未支援的 control 應回 RICcontrolFailure (見 _handle_control_req
                    # 已實作的 negative case), 但 codec 內部 bug / sim CU 通訊異常等
                    # 不可預期錯誤一律不殺連線.
                    try:
                        _dispatch_pdu(sock, pdu)
                    except Exception:
                        logger.exception(
                            "PDU dispatch failed (%d bytes) — keeping SCTP alive", len(pdu),
                        )
                        try:
                            event_ring.record_control_failure(
                                "dispatch exception", style=0, action=0,
                            )
                        except Exception:
                            pass
            # if E2 Setup failed OR inner loop broke (peer closed) → reconnect.
            # 停所有 indication thread 避免它們繼續寫已死的 socket 累 send 失敗.
            _stop_all_indication_threads()

        except (socket.error, OSError) as exc:  # noqa: F841 — re-raised below
            _stop_all_indication_threads()
            logger.warning("SCTP error: %s — will reconnect after %ds", exc, backoff_sec)
            MemoryStateBusinessService.update_state(
                registry,
                sctp_connected=False,
                last_disconnect_at_ms=_now_ms(),
                last_error=f"socket: {exc!r}",
                e2_setup_completed=False,
                accepted_ran_function_ids=[],
                rejected_ran_function_ids=[],
            )
        except Exception as exc:
            logger.exception("SCTP loop unexpected error — will reconnect")
            MemoryStateBusinessService.update_state(
                registry, last_error=f"unexpected: {exc!r}",
            )
        finally:
            try:
                sock.close()
            except Exception:
                pass
            MemoryStateBusinessService.update_state(
                registry,
                sctp_connected=False,
                last_disconnect_at_ms=_now_ms(),
            )

        time.sleep(backoff_sec)


def start_if_enabled() -> None:
    """Called from AppConfig.ready(). Idempotent."""
    global _thread

    if _started_flag.is_set():
        return
    _started_flag.set()

    if not is_enabled():
        logger.info("SCTP loop disabled (E2_ADAPTER_LINK_ENABLED!=1) — skeleton-only mode")
        return

    host, port = link_target()
    if not host:
        logger.warning("SCTP loop enabled but RIC_E2TERM_HOST unset — refusing to start")
        return

    logger.info("Starting SCTP background thread → %s:%d", host, port)
    _thread = threading.Thread(target=_link_loop, args=(host, port), daemon=True)
    _thread.start()


# ── PDU dispatcher + handlers (P2.8.2-B) ──────────────────────

def _dispatch_pdu(sock, pdu_bytes: bytes) -> None:
    """Decode incoming PDU and route to handler based on procedureCode."""
    from main.apps.e2_adapter.services.optional.codec import e2ap_codec
    try:
        decoded = e2ap_codec.decode_e2ap_pdu(pdu_bytes)
    except Exception as exc:
        logger.exception("decode incoming PDU failed (%d bytes)", len(pdu_bytes))
        return

    outcome_choice, msg = decoded
    if outcome_choice != "initiatingMessage":
        logger.debug("recv non-initiating PDU type=%s — ignoring", outcome_choice)
        return

    proc_code = msg.get("procedureCode")
    inner_choice = msg["value"][0]
    logger.info("recv PDU procCode=%d type=%s len=%d", proc_code, inner_choice, len(pdu_bytes))

    if proc_code == 8 and inner_choice == "RICsubscriptionRequest":  # RIC Subscription
        _handle_sub_req(sock, msg["value"][1])
    elif proc_code == 4 and inner_choice == "RICcontrolRequest":     # RIC Control
        _handle_control_req(sock, pdu_bytes)
    elif proc_code == 9 and inner_choice == "RICsubscriptionDeleteRequest":
        logger.info("RIC Subscription Delete Request received — TODO (sim CU sub_delete)")
    else:
        logger.info("Unhandled procCode=%d inner=%s — skip", proc_code, inner_choice)


def _handle_sub_req(sock, sub_req_value: dict) -> None:
    """Decode RIC_SUB_REQ → POST sim CU /Subscription/create → encode SUB_RESP → SCTP send.

    Then start indication producer thread for that subscription.
    """
    from main.apps.e2_adapter.services.optional.codec import (
        e2ap_codec, e2_subscription_codec, e2sm_kpm_codec,
    )
    from main.apps.e2_adapter.services.optional.sim_bridge import sim_http_client

    # Re-encode the sub_req to pass through decoder（其實 decoder 拿原 bytes 比較直接，
    # 但這裡 PDU 已是 dict 格式，直接抽 IEs）
    ric_req_id = {"requestor_id": 0, "instance_id": 0}
    ran_func_id = 0
    sub_details: dict = {}
    for ie in sub_req_value.get("protocolIEs", []):
        ie_id = ie.get("id")
        if ie_id == 29:
            v = ie["value"][1]
            ric_req_id = {"requestor_id": v.get("ricRequestorID", 0),
                          "instance_id": v.get("ricInstanceID", 0)}
        elif ie_id == 5:
            ran_func_id = int(ie["value"][1])
        elif ie_id == 30:
            sub_details = ie["value"][1]

    event_trig_bytes = sub_details.get("ricEventTriggerDefinition", b"")
    actions = sub_details.get("ricAction-ToBeSetup-List", [])

    # Decode period from KPM event trigger Format1
    rt_codec = e2_subscription_codec
    period_ms = rt_codec._decode_event_trigger_period(event_trig_bytes)

    # 解每個 action 的 metric list（取第一個 action 即可，xApp 通常 1 sub 1 action）
    action_specs = []
    for act_ie in actions:
        act = act_ie["value"][1]
        action_specs.append({
            "action_id": act.get("ricActionID"),
            "action_type": act.get("ricActionType"),
            "metrics": rt_codec._decode_action_metrics(act.get("ricActionDefinition", b"")),
        })

    if not action_specs:
        logger.warning("SUB_REQ has 0 actions — sending empty SUB_RESP")
        return

    primary_action = action_specs[0]
    sim_payload = {
        "service_model": "KPM" if ran_func_id == 2 else "RC",
        "ran_function_id": ran_func_id,
        "ric_req_id": ric_req_id,
        "event_trigger": {"format": 1, "report_period_ms": period_ms},
        "action_definition": {
            "metrics": primary_action["metrics"],
            "report_period_ms": period_ms,
            "ue_filter": {},
        },
    }

    # Step: POST sim CU /Subscription/create
    sim_resp = sim_http_client.call_subscription_create(sim_payload)
    if sim_resp is None or not sim_resp.get("subscription_id"):
        logger.error("sim CU subscription/create failed — cannot ack SUB_REQ")
        return

    sub_id = sim_resp["subscription_id"]
    logger.info("SUB_REQ → sim CU created sub_id=%s period=%dms metrics=%s",
                sub_id, period_ms, primary_action["metrics"])
    event_ring.record_sub_req_recv(
        sub_id=sub_id, ric_req_id=ric_req_id, ran_func_id=ran_func_id,
        metrics=primary_action["metrics"], period_ms=period_ms,
    )

    # Step: encode + send SUB_RESP
    admitted_ids = [a["action_id"] for a in action_specs]
    try:
        resp_bytes = e2_subscription_codec.encode_ric_subscription_response(
            ric_req_id=ric_req_id,
            ran_function_id=ran_func_id,
            admitted_action_ids=admitted_ids,
        )
    except Exception:
        logger.exception("encode RIC_SUB_RESP failed")
        return

    if not _send_sctp(sock, resp_bytes):
        logger.error("SCTP send SUB_RESP failed")
        return

    from main.apps.e2_adapter.models.connection_state import get_registry
    from main.apps.e2_adapter.services.business.memory_state_operations import (
        MemoryStateBusinessService,
    )
    registry = get_registry()
    MemoryStateBusinessService.update_state(
        registry, pdu_sent_count=registry.get_connection().pdu_sent_count + 1,
    )
    logger.info("SUB_RESP sent (%d bytes) — admitted actions=%s", len(resp_bytes), admitted_ids)
    event_ring.record_sub_resp_sent(sub_id=sub_id, admitted_action_ids=admitted_ids,
                                     pdu_size=len(resp_bytes))

    # Step: start indication producer thread
    _start_producer(sock, sub_id, ric_req_id, ran_func_id, admitted_ids[0], period_ms)


def _start_producer(sock, sub_id: str, ric_req_id: dict, ran_func_id: int,
                     action_id: int, period_ms: int) -> None:
    """Common helper：啟動一個 indication producer thread + 註冊到 _ACTIVE_SUBS。"""
    sub_signature = f"{ric_req_id['requestor_id']}-{ric_req_id['instance_id']}-{ran_func_id}"
    with _SUBS_LOCK:
        old = _ACTIVE_SUBS.pop(sub_signature, None)
        if old:
            old["stop"].set()

        stop_evt = threading.Event()
        meta = {
            "sub_id": sub_id,
            "ric_req_id": ric_req_id,
            "ran_func_id": ran_func_id,
            "action_id": action_id,
            "period_ms": period_ms,
            "sn": 0,
            "stop": stop_evt,
            "_sub_signature": sub_signature,   # for self-cleanup on SubNotFoundError
        }
        t = threading.Thread(
            target=_indication_producer_loop,
            args=(sock, meta),
            daemon=True,
        )
        meta["thread"] = t
        _ACTIVE_SUBS[sub_signature] = meta
        t.start()
    logger.info("indication producer started sub_id=%s sig=%s", sub_id, sub_signature)


# NOTE (2026-05-08, removed): 砍掉 _restore_producers_from_sim().
# 原本意圖是 adapter 重啟後從 sim CU /Subscription/list 重建 producer thread,
# 但 sim CU 端的 sub_id 只有 sim 跟 adapter 雙方認得 — RIC 端早已遺忘 (RIC R-NIB
# 5min cleanup), xApp 也沒在 RIC 重新訂閱. adapter 自己造的 ghost producer 把
# RIC_INDICATION 送過去, RIC 找不到對應 RIC subscription → silently drop, 結果是
# 25 小時送 27262 個 indication 沒人收, log 灌爆 45 GB.
# 正確設計: producer 只應在收到 RIC_SUB_REQ 時啟動 (見 _dispatch_pdu).
# 對 demo 影響: adapter 重啟後 _ACTIVE_SUBS=空, 等 xApp 透過 RIC 重發 SUB_REQ.

def _indication_producer_loop(sock, meta: dict) -> None:
    """Per-subscription daemon thread: poll sim CU + encode KPM Indication + SCTP send."""
    from main.apps.e2_adapter.models.connection_state import get_registry
    from main.apps.e2_adapter.services.business.memory_state_operations import (
        MemoryStateBusinessService,
    )
    from main.apps.e2_adapter.services.optional.codec import e2_subscription_codec, e2sm_kpm_codec
    from main.apps.e2_adapter.services.optional.sim_bridge import sim_http_client

    registry = get_registry()
    sub_id = meta["sub_id"]
    period_sec = max(0.1, meta["period_ms"] / 1000.0)
    logger.info("indication producer started sub_id=%s period=%.1fs", sub_id, period_sec)

    poll_count = 0
    sent_count = 0
    while not meta["stop"].is_set():
        try:
            poll_resp = sim_http_client.poll_indication(sub_id)
        except sim_http_client.SubNotFoundError as exc:
            # Y1: sim CU 重啟後 in-memory subscription registry 被清空.
            # RIC 那邊還有 cached sub_id, 不會自動重發 SUB_REQ → 送 E2 Reset
            # 強迫 RIC 清掉 sub state 重新訂閱 (對齊真實 OAI CU restart 行為).
            logger.warning(
                "indication producer stopping — sim CU lost sub %s (%s). "
                "Sending E2 Reset to RIC to force re-subscribe.", sub_id, exc,
            )
            event_ring.append("indication_producer_stop", sub_id=sub_id, reason="sim_lost_sub")
            sub_signature = meta.get("_sub_signature")
            if sub_signature:
                with _SUBS_LOCK:
                    _ACTIVE_SUBS.pop(sub_signature, None)
            _send_e2_reset(sock, reason=f"sim CU lost sub {sub_id}")
            return
        except Exception:
            logger.exception("poll_indication exception")
            poll_resp = None
        poll_count += 1

        if poll_resp is None:
            if poll_count % 10 == 1:
                logger.info("poll_indication returned None (sub=%s, poll #%d)", sub_id, poll_count)
            meta["stop"].wait(period_sec)
            continue

        ind_count = len(poll_resp.get("indications", []))
        if poll_count % 10 == 1 or ind_count > 0:
            logger.info("poll #%d sub=%s indications=%d sent_so_far=%d",
                        poll_count, sub_id, ind_count, sent_count)

        for ind in poll_resp.get("indications", []):
            # sim CU 結構：ind = {indication_header, indication_message}
            ind_msg = ind.get("indication_message") or {}
            ind_hdr = ind.get("indication_header") or {}
            # Format 3 ueMeasReportList SIZE(1..N) — empty list 違反 spec，skip
            if not (ind_msg.get("ue_meas_report_lst") or []):
                continue
            # snapshot — 給 Dashboard KPM panel 看 metric 數值（在編 PDU 之前記）
            kpm_snapshot.get_ring().append_indication(sub_id, ind)
            try:
                msg_bytes = e2sm_kpm_codec.encode_kpm_indication_message(ind_msg)
                hdr_bytes = e2sm_kpm_codec.encode_kpm_indication_header(
                    int(ind_hdr.get("timestamp_ms", 0))
                )
                meta["sn"] = (meta["sn"] + 1) & 0xFFFF
                pdu = e2_subscription_codec.encode_ric_indication(
                    ric_req_id=meta["ric_req_id"],
                    ran_function_id=meta["ran_func_id"],
                    action_id=meta["action_id"],
                    indication_sn=meta["sn"],
                    indication_header=hdr_bytes,
                    indication_message=msg_bytes,
                    indication_type="report",
                )
            except Exception:
                logger.exception("encode RIC_INDICATION failed for sub %s", sub_id)
                continue

            if _send_sctp(sock, pdu):
                MemoryStateBusinessService.update_state(
                    registry,
                    pdu_sent_count=registry.get_connection().pdu_sent_count + 1,
                )
                sent_count += 1
                if sent_count <= 3 or sent_count % 10 == 0:
                    logger.info("RIC_INDICATION sent sub=%s sn=%d %d bytes (total=%d)",
                                sub_id, meta["sn"], len(pdu), sent_count)
                ue_count = len((ind_msg or {}).get("ue_meas_report_lst") or [])
                event_ring.record_indication_sent(sub_id=sub_id, sn=meta["sn"],
                                                   pdu_size=len(pdu), ue_count=ue_count)

        meta["stop"].wait(period_sec)

    logger.info("indication producer stopped sub_id=%s", sub_id)


def _stop_all_indication_threads() -> None:
    """SCTP 斷線時呼叫，清掉所有 indication producer thread。"""
    with _SUBS_LOCK:
        for sig, meta in list(_ACTIVE_SUBS.items()):
            meta["stop"].set()
        _ACTIVE_SUBS.clear()


def _send_e2_reset(sock, reason: str, cause_misc: str = "om-intervention") -> bool:
    """Y1: Send E2 Reset Request to RIC. Debounced to once per 30s.

    Triggered when sim CU loses subscription registry (e.g. CU restart wiped
    in-memory state). RIC keeps stale sub_id, won't re-issue SUB_REQ — Reset
    forces RIC to clear all sub state and re-subscribe.

    Aligns with real OAI: CU restart sends E2 Reset; doesn't wait 5min backoff.

    Returns True if Reset was sent, False if debounced or send failed.
    """
    global _LAST_RESET_SENT_MS
    from main.apps.e2_adapter.models.connection_state import get_registry
    from main.apps.e2_adapter.services.business.memory_state_operations import (
        MemoryStateBusinessService,
    )
    from main.apps.e2_adapter.services.optional.codec import e2ap_codec

    with _RESET_LOCK:
        now = _now_ms()
        if now - _LAST_RESET_SENT_MS < _RESET_COOLDOWN_MS:
            logger.debug("E2 Reset debounced (last sent %dms ago < %dms cooldown)",
                         now - _LAST_RESET_SENT_MS, _RESET_COOLDOWN_MS)
            return False
        try:
            pdu = e2ap_codec.encode_e2_reset_request(cause_misc=cause_misc)
        except Exception:
            logger.exception("encode_e2_reset_request failed")
            return False
        if not _send_sctp(sock, pdu):
            logger.error("SCTP send E2 Reset failed")
            return False
        _LAST_RESET_SENT_MS = now

    registry = get_registry()
    MemoryStateBusinessService.update_state(
        registry, pdu_sent_count=registry.get_connection().pdu_sent_count + 1,
    )
    logger.info("E2 Reset sent (%d bytes) cause=misc.%s reason=%s",
                len(pdu), cause_misc, reason)
    event_ring.append("e2_reset_sent", reason=reason, cause_misc=cause_misc,
                       pdu_size=len(pdu))
    return True


# ── RIC_CONTROL_REQ handler (P2.8.6) ──────────────────────────

# Supported (style, action) combos that map to a sim CU action
_SUPPORTED_RC_STYLES = {(2, 6), (3, 1)}
# Required RANParameter IDs per (style, action). Missing → control-message-invalid.
_REQUIRED_RAN_PARAMS: dict[tuple[int, int], set[int]] = {
    (2, 6): {1, 2, 3},   # min, max, dedicated PRB ratio
    (3, 1): {1},         # target primary cell ID
}
# Sim CU's hardcoded RC ran_function_id (must match rc-probe expectation)
_RC_RAN_FUNCTION_ID = 3


def _send_control_failure(sock, ric_req_id: dict, ran_func_id: int,
                            cause: tuple[str, str], call_process_id: bytes,
                            style: int, action: int, reason: str) -> None:
    """Encode + send RIC_CONTROL_FAILURE. cause = (group, value) e.g.
    ("ricRequest", "ran-function-id-invalid")."""
    from main.apps.e2_adapter.models.connection_state import get_registry
    from main.apps.e2_adapter.services.business.memory_state_operations import (
        MemoryStateBusinessService,
    )
    from main.apps.e2_adapter.services.optional.codec import e2sm_rc_codec

    try:
        pdu = e2sm_rc_codec.encode_ric_control_failure(
            ric_req_id=ric_req_id,
            ran_function_id=ran_func_id,
            cause=cause,
            call_process_id=call_process_id,
        )
    except Exception:
        logger.exception("encode RIC_CONTROL_FAILURE failed")
        event_ring.record_control_failure("encode failure pdu fail",
                                            style=style, action=action)
        return

    if not _send_sctp(sock, pdu):
        logger.error("SCTP send RIC_CONTROL_FAILURE failed")
        event_ring.record_control_failure("sctp send failure pdu fail",
                                            style=style, action=action)
        return

    registry = get_registry()
    MemoryStateBusinessService.update_state(
        registry, pdu_sent_count=registry.get_connection().pdu_sent_count + 1,
    )
    event_ring.append("control_failure_sent", style=style, action=action,
                       cause_group=cause[0], cause_value=cause[1],
                       reason=reason, pdu_size=len(pdu))
    logger.info("RIC_CONTROL_FAILURE sent (%d bytes) cause=%s::%s reason=%s",
                len(pdu), cause[0], cause[1], reason)


def _handle_control_req(sock, raw_pdu: bytes) -> None:
    """Decode RIC_CONTROL_REQ → POST sim CU /Control/request → encode ACK/FAILURE → SCTP send.

    Style 3/Action 1 → control_handover  (CCO, ES)
    Style 2/Action 6 → control_slice_level_prb_quota  (IM, ES)

    FAILURE cases (per RIC team rc-probe contract):
      ran_function_id != 3        → ricRequest::ran-function-id-invalid
      (style, action) unsupported → ricRequest::action-not-supported
      ranParameter-ID 不認得       → ricRequest::control-message-invalid
    sim CU dispatch error → 仍回 ACK (內部問題不是 RC 通訊問題).
    """
    from main.apps.e2_adapter.models.connection_state import get_registry
    from main.apps.e2_adapter.services.business.memory_state_operations import (
        MemoryStateBusinessService,
    )
    from main.apps.e2_adapter.services.optional.codec import e2sm_rc_codec
    from main.apps.e2_adapter.services.optional.sim_bridge import sim_http_client

    registry = get_registry()

    try:
        decoded = e2sm_rc_codec.decode_ric_control_request(raw_pdu)
    except Exception as exc:
        logger.exception("decode RIC_CONTROL_REQ failed")
        event_ring.record_control_failure(f"decode error: {exc!r}")
        return

    style = decoded.get("style_type", 0)
    action = decoded.get("action_id", 0)
    ueid = decoded.get("ueid", {})
    ric_req_id = decoded.get("ric_req_id", {})
    ran_func_id = decoded.get("ran_function_id", 0)
    call_proc_id_hex = decoded.get("call_process_id", "")
    call_proc_bytes = bytes.fromhex(call_proc_id_hex) if call_proc_id_hex else b""
    params = decoded.get("ran_params", {}) or {}

    # ── Negative case 1: wrong ran_function_id ─────────────────
    if ran_func_id != _RC_RAN_FUNCTION_ID:
        _send_control_failure(
            sock, ric_req_id, ran_func_id,
            cause=("ricRequest", "ran-function-id-invalid"),
            call_process_id=call_proc_bytes,
            style=style, action=action,
            reason=f"got ran_function_id={ran_func_id}, expected={_RC_RAN_FUNCTION_ID}",
        )
        return

    # ── Negative case 2: unsupported (style, action) ───────────
    if (style, action) not in _SUPPORTED_RC_STYLES:
        _send_control_failure(
            sock, ric_req_id, ran_func_id,
            cause=("ricRequest", "action-not-supported"),
            call_process_id=call_proc_bytes,
            style=style, action=action,
            reason=f"(style={style}, action={action}) not in supported list",
        )
        return

    # ── Negative case 3: ranParameter-ID 不認得 / missing ──────
    required_ids = _REQUIRED_RAN_PARAMS.get((style, action), set())
    present_ids = set(params.keys())
    missing = required_ids - present_ids
    extra = present_ids - required_ids
    if missing or extra:
        _send_control_failure(
            sock, ric_req_id, ran_func_id,
            cause=("ricRequest", "control-message-invalid"),
            call_process_id=call_proc_bytes,
            style=style, action=action,
            reason=f"ranP missing={sorted(missing)} extra={sorted(extra)}",
        )
        return

    # 給 decoder hint：sim 的 ranName 當 control_header.node（PRB quota 不指定 cell_id 時用）
    try:
        node_id = sim_http_client.fetch_e2_node_id()
        decoded["_node_hint"] = (node_id or {}).get("expected_ran_name", "")
    except Exception:
        decoded["_node_hint"] = ""

    sim_payload = e2sm_rc_codec.to_sim_control_payload(decoded)
    if sim_payload is None:
        # 理論上前面 (style,action) check 已擋掉,這是 defensive
        _send_control_failure(
            sock, ric_req_id, ran_func_id,
            cause=("ricRequest", "action-not-supported"),
            call_process_id=call_proc_bytes,
            style=style, action=action,
            reason="to_sim_control_payload returned None (post-validation)",
        )
        return

    sim_action = sim_payload.get("action", "?")
    event_ring.record_control_req_recv(style=style, action=action,
                                         sim_action=sim_action, ueid=ueid)
    logger.info(
        "RIC_CONTROL_REQ recv style=%d action=%d → sim action=%s ueid=%s",
        style, action, sim_action, ueid,
    )

    # Step: forward to sim CU (sim dispatch error 不轉 FAILURE,只記 outcome)
    sim_resp = sim_http_client.call_control_request(sim_payload)
    sim_ok = sim_resp is not None
    outcome = "ok" if sim_ok else "sim_error"
    if not sim_ok:
        logger.warning("sim CU /Control/request returned None for style=%d action=%d",
                       style, action)

    # Step: encode + send RIC_CONTROL_ACK
    try:
        ack = e2sm_rc_codec.encode_ric_control_ack(
            ric_req_id=ric_req_id,
            ran_function_id=ran_func_id,
            call_process_id=call_proc_bytes,
        )
    except Exception:
        logger.exception("encode RIC_CONTROL_ACK failed")
        event_ring.record_control_failure("encode ack fail", style=style, action=action)
        return

    if not _send_sctp(sock, ack):
        logger.error("SCTP send RIC_CONTROL_ACK failed")
        event_ring.record_control_failure("sctp send ack fail", style=style, action=action)
        return

    MemoryStateBusinessService.update_state(
        registry, pdu_sent_count=registry.get_connection().pdu_sent_count + 1,
    )
    event_ring.record_control_ack_sent(style=style, action=action, sim_action=sim_action,
                                         pdu_size=len(ack), outcome=outcome)
    logger.info("RIC_CONTROL_ACK sent (%d bytes) — style=%d action=%d outcome=%s",
                len(ack), style, action, outcome)
