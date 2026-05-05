"""DU 啟動時送 F1Setup 給 CU(retry up to 60s)。

對應 OAI: openair2/F1AP/f1ap_du_task.c 的 F1AP_DU_REGISTER_REQ → 送 F1 Setup Request。
"""
from __future__ import annotations

import threading
import time

from ran_sim_protocol.common import CellConfig
from ran_sim_protocol.f1ap import F1Setup

from main.apps.f1ap_du.services.business.cu_client_operations import CuClientBusinessService
from main.apps.f1ap_du.services.optional.message_codec.f1ap_codec import encode_f1_setup
from main.utils.env_loader import get_int
from main.utils.logger import get_logger

logger = get_logger(__name__)

_started = False
_done = threading.Event()
_lock = threading.Lock()


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


def _bootstrap_loop(max_retries: int = 20, interval_s: float = 3.0) -> None:
    """每 3 秒嘗試一次,最多 60 秒。"""
    for i in range(max_retries):
        try:
            msg = _build_setup_message()
            payload = encode_f1_setup(msg)
            resp = CuClientBusinessService.post_du_setup(payload, timeout=3.0)
            if resp is not None:
                logger.info("F1Setup accepted by CU (attempt %d)", i + 1)
                _done.set()
                return
        except Exception as e:
            logger.warning("F1Setup attempt %d errored: %s", i + 1, e)
        time.sleep(interval_s)
    logger.error("F1Setup failed after %d attempts; will retry on next start", max_retries)


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
