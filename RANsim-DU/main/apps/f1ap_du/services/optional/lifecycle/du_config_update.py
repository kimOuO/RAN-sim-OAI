"""gNB-DU Configuration Update outbound (3GPP TS 38.473 §8.2.4)。

F1Setup 完成後,DU 若新增 / 修改 / 刪除 cell,主動通知 CU。

OAI 對應:
  - openair2/F1AP/f1ap_du_interface_management.c::DU_send_gNB_DU_CONFIGURATION_UPDATE
  - procedure code 3 (initiating message)

設計:
  - F1 setup 還沒 ACTIVE → 不發(F1Setup 會帶完整 served_cells 過去,免重複)
  - transaction_id 在 module-level 自增,可被 reset() 重設(測試用)
  - send() 是 fire-and-best-effort,失敗回 None,呼叫端決定要不要 retry
"""
from __future__ import annotations

import threading
from typing import Any

from ran_sim_protocol.common import CellConfig
from ran_sim_protocol.f1ap import GnbDuConfigurationUpdate

from main.apps.f1ap_du.services.business.cu_client_operations import CuClientBusinessService
from main.apps.f1ap_du.services.optional.lifecycle.du_bootstrap import is_setup_done
from main.utils.env_loader import get_int
from main.utils.logger import get_logger
from ran_sim_protocol import to_dict

logger = get_logger(__name__)

_tx_counter = 0
_tx_lock = threading.Lock()


def _next_tx_id() -> int:
    global _tx_counter
    with _tx_lock:
        _tx_counter += 1
        return _tx_counter


def reset_tx_counter() -> None:
    """測試用 — reset transaction id。"""
    global _tx_counter
    with _tx_lock:
        _tx_counter = 0


def get_tx_counter() -> int:
    with _tx_lock:
        return _tx_counter


def send(
    *,
    cells_to_add: list[CellConfig] | None = None,
    cells_to_modify: list[CellConfig] | None = None,
    cells_to_delete: list[str] | None = None,
    force: bool = False,
    timeout: float = 3.0,
) -> dict[str, Any] | None:
    """送 gNB-DU Configuration Update 給 CU。

    Args:
      cells_to_add / cells_to_modify / cells_to_delete: 變更內容
      force: True 即使 F1 還沒 ACTIVE 也送(整合測試用)
      timeout: HTTP timeout

    Returns:
      CU 的 ACK body(成功 + 200 + JSON)或 None(F1 not active / network fail)。
    """
    cells_to_add = cells_to_add or []
    cells_to_modify = cells_to_modify or []
    cells_to_delete = cells_to_delete or []

    if not (cells_to_add or cells_to_modify or cells_to_delete):
        logger.debug("config update with no changes — skipping")
        return None

    if not force and not is_setup_done():
        logger.info(
            "F1 not active yet (cells_to_add=%d modify=%d delete=%d) — skipping config update",
            len(cells_to_add), len(cells_to_modify), len(cells_to_delete),
        )
        return None

    msg = GnbDuConfigurationUpdate(
        gnb_du_id=get_int("SIM_GNB_DU_ID", 1),
        transaction_id=_next_tx_id(),
        served_cells_to_add=cells_to_add,
        served_cells_to_modify=cells_to_modify,
        served_cells_to_delete=cells_to_delete,
    )
    payload = to_dict(msg)
    resp = CuClientBusinessService.post_du_configuration_update(payload, timeout=timeout)
    if resp is None:
        logger.warning("DU Config Update tid=%s — CU unreachable / non-OK", msg.transaction_id)
        return None

    # 嘗試解 ACK 看 accepted 旗標(支援 wrapped {data:{...}} 跟 bare 兩種)
    inner = resp.get("data") if isinstance(resp.get("data"), dict) else resp
    accepted = bool(inner.get("accepted", True)) if isinstance(inner, dict) else True
    logger.info(
        "DU Config Update tid=%s accepted=%s (add=%d modify=%d delete=%d)",
        msg.transaction_id, accepted,
        len(cells_to_add), len(cells_to_modify), len(cells_to_delete),
    )
    return resp


def cell_state_to_config(cell) -> CellConfig:
    """把 mac.models.CellState ORM 物件轉成 protocol CellConfig dataclass。"""
    return CellConfig(
        cell_id=cell.cell_id,
        pci=cell.pci,
        frequency_ghz=cell.freq_ghz,
        bandwidth_mhz=cell.bw_mhz,
        served_plmn=cell.served_plmn,
    )
