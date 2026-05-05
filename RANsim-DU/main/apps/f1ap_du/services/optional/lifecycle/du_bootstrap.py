"""DU 啟動時送 F1Setup 給 CU,解析回應、寫 F1Session,retry on network error。

對應 OAI: openair2/F1AP/f1ap_du_task.c 的 F1AP_DU_REGISTER_REQ → 送 F1 Setup Request。

State machine:
  INIT      — 還沒送出
  SETUP_SENT — 已送 F1 Setup Request,等 response
  ACTIVE    — 收到 accepted=true,記下 transaction_id
  FAILED    — 收到 accepted=false,explicit reject(不再 retry)
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from ran_sim_protocol.common import CellConfig
from ran_sim_protocol.f1ap import F1Setup

from main.apps.f1ap_du.services.business.cu_client_operations import CuClientBusinessService
from main.apps.f1ap_du.services.optional.message_codec.f1ap_codec import encode_f1_setup
from main.utils.env_loader import get_int, get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)


# ─── State / 控制旗標 ────────────────────────────────────────────────


@dataclass
class BootstrapState:
    state: str = "INIT"
    transaction_id: int = 0
    attempts: int = 0
    last_response: dict[str, Any] | None = None


_state = BootstrapState()
_state_lock = threading.Lock()
_started = False
_done = threading.Event()
_lock = threading.Lock()


def get_state() -> BootstrapState:
    with _state_lock:
        return BootstrapState(
            state=_state.state,
            transaction_id=_state.transaction_id,
            attempts=_state.attempts,
            last_response=dict(_state.last_response) if _state.last_response else None,
        )


def reset_state() -> None:
    """測試 / re-bootstrap 用。"""
    global _started
    with _state_lock:
        _state.state = "INIT"
        _state.transaction_id = 0
        _state.attempts = 0
        _state.last_response = None
    _done.clear()
    with _lock:
        _started = False


# ─── 訊息建構 / 解析 ──────────────────────────────────────────────────


def _build_setup_message() -> F1Setup:
    """讀 cell_state 表組 F1Setup;若 DB 還空,送一個 default cell。"""
    try:
        from main.apps.mac.models.cell_state import CellState
        cells = list(CellState.objects.all())
    except Exception:
        cells = []

    served_cells: list[CellConfig] = []
    if cells:
        for c in cells:
            served_cells.append(
                CellConfig(
                    cell_id=c.cell_id,
                    pci=c.pci,
                    frequency_ghz=c.freq_ghz,
                    bandwidth_mhz=c.bw_mhz,
                    served_plmn=c.served_plmn,
                ),
            )
    else:
        served_cells.append(
            CellConfig(
                cell_id="default-cell-0", pci=0, frequency_ghz=3.5, bandwidth_mhz=100.0,
            ),
        )

    return F1Setup(
        gnb_du_id=get_int("SIM_GNB_DU_ID", 1),
        served_cells=served_cells,
    )


def _parse_setup_response(body: dict[str, Any]) -> tuple[bool, int]:
    """從 response body 取 (accepted, transaction_id)。

    支援兩種 schema:
      - wrapped:  {"status":"success","data":{"accepted":true,"transaction_id":1}}
      - bare:     {"accepted":true,"transaction_id":1}
    取不到欄位時 fallback (False, 0)。
    """
    if not isinstance(body, dict):
        return False, 0
    inner = body.get("data") if isinstance(body.get("data"), dict) else body
    accepted = bool(inner.get("accepted", False))
    try:
        tid = int(inner.get("transaction_id", 0))
    except (TypeError, ValueError):
        tid = 0
    return accepted, tid


# ─── F1Session 持久化 ─────────────────────────────────────────────────


def _persist_session(host: str, port: int, gnb_du_id: int, transaction_id: int, state: str) -> None:
    """寫 F1Session table — fail silently 但 log,不要因 DB 問題擋掉 retry loop。"""
    try:
        from main.apps.f1ap_du.models.f1_session import F1Session
        from main.apps.f1ap_du.services.business.relational_db_operations import (
            RelationalDbBusinessService,
        )
        from main.apps.f1ap_du.services.common.timestamp_service import TimestampService
        from main.apps.f1ap_du.services.common.uuid_service import UUIDService

        f1_uuid = UUIDService.generate_uuid("f1_session", str(gnb_du_id))
        ts = TimestampService.now_ms()
        RelationalDbBusinessService.upsert_entity(
            F1Session, "f1_uuid", f1_uuid,
            {
                "f1_uuid": f1_uuid,
                "gnb_du_id": gnb_du_id,
                "cu_host": host,
                "cu_port": port,
                "transaction_id": transaction_id,
                "state": state,
                "last_setup_at": ts if state == "ACTIVE" else None,
                "f1_session_updated_at": ts,
            },
        )
    except Exception as e:
        logger.warning("F1Session persist skipped (%s): %s", state, e)


# ─── 主流程 ────────────────────────────────────────────────────────────


def attempt_setup(timeout: float = 3.0) -> str:
    """單次 F1 Setup 嘗試。回傳結果 state(`ACTIVE` / `FAILED` / `SETUP_SENT`)。

    `SETUP_SENT` 表示 network 失敗、值得 retry。
    `ACTIVE` / `FAILED` 都是 terminal。
    """
    cu_host = get_str("HTTP_CU_HOST", "cu")
    cu_port = get_int("HTTP_CU_PORT", 8000)
    msg = _build_setup_message()
    payload = encode_f1_setup(msg)

    with _state_lock:
        _state.state = "SETUP_SENT"
        _state.attempts += 1
    _persist_session(cu_host, cu_port, msg.gnb_du_id, 0, "SETUP_SENT")

    resp = CuClientBusinessService.post_du_setup(payload, timeout=timeout)
    if resp is None:
        logger.warning("F1Setup attempt %d: CU unreachable / no body", _state.attempts)
        return "SETUP_SENT"

    accepted, tid = _parse_setup_response(resp)
    with _state_lock:
        _state.last_response = resp
        _state.transaction_id = tid

    if accepted:
        with _state_lock:
            _state.state = "ACTIVE"
        _persist_session(cu_host, cu_port, msg.gnb_du_id, tid, "ACTIVE")
        _done.set()
        logger.info("F1Setup ACCEPTED tid=%s (attempt %d)", tid, _state.attempts)
        return "ACTIVE"

    with _state_lock:
        _state.state = "FAILED"
    _persist_session(cu_host, cu_port, msg.gnb_du_id, tid, "FAILED")
    logger.error("F1Setup REJECTED by CU (attempt %d, tid=%s)", _state.attempts, tid)
    return "FAILED"


def _bootstrap_loop(max_retries: int = 20, interval_s: float = 3.0) -> None:
    """背景 retry 直到 ACTIVE 或 FAILED 或耗完 retry。"""
    for _ in range(max_retries):
        outcome = attempt_setup()
        if outcome in ("ACTIVE", "FAILED"):
            return  # terminal,不再 retry
        time.sleep(interval_s)
    logger.error(
        "F1Setup gave up after %d attempts; final state=%s",
        max_retries, get_state().state,
    )


def start_bootstrap_in_background() -> None:
    global _started
    with _lock:
        if _started:
            return
        _started = True
    t = threading.Thread(target=_bootstrap_loop, daemon=True, name="du-bootstrap")
    t.start()


def is_setup_done() -> bool:
    return _done.is_set()
