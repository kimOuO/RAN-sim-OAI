"""HTTP client to DU. Mirrors OAI's f1ap_cu_*.c → SCTP send path.

OAI ref:
  - openair2/F1AP/f1ap_cu_rrc_message_transfer.c (CU_send_DL_RRC_MESSAGE_TRANSFER)
  - openair2/F1AP/f1ap_cu_ue_context_management.c (CU_send_UE_CONTEXT_SETUP_REQUEST)
"""
from __future__ import annotations

from typing import Any

import requests

from main.utils.env_loader import get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)

_TIMEOUT_SEC = 5.0


def _du_base_url() -> str:
    host = get_str("HTTP_DU_HOST")
    port = get_str("HTTP_DU_PORT", "8000")
    scheme = get_str("HTTP_DU_SCHEME", "http")
    if not host:
        return ""
    return f"{scheme}://{host}:{port}"


class DuClientBusinessService:
    """Issue HTTP POST to the DU's F1AP router."""

    @staticmethod
    def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
        base = _du_base_url()
        if not base:
            logger.warning("DU base URL not configured; skipping POST %s", path)
            return {"success": False, "skipped": True}
        url = f"{base}{path}"
        try:
            resp = requests.post(url, json=payload, timeout=_TIMEOUT_SEC)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("DU call %s failed: %s", url, exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def post_dl_rrc_message(payload: dict[str, Any]) -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/F1AP/F1ApRouter/dl_rrc_message", payload,
        )

    @staticmethod
    def post_ue_context_setup(payload: dict[str, Any]) -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/F1AP/F1ApRouter/ue_context_setup", payload,
        )

    @staticmethod
    def post_ue_context_modification(payload: dict[str, Any]) -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/F1AP/F1ApRouter/ue_context_modification", payload,
        )

    @staticmethod
    def post_ue_context_release(payload: dict[str, Any]) -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/F1AP/F1ApRouter/ue_context_release", payload,
        )

    @staticmethod
    def read_mac_cells() -> list[str]:
        """讀 DU 當前的 cell 清單，回 cell_id list。
        AK12: release_stale 用來檢查 UeContext.serving_cell 是不是 orphan（指到
        已經不存在的 cell）。空 list 表示讀不到 — 呼叫端應該降級處理。"""
        resp = DuClientBusinessService._post(
            "/api/v0.1/DU/MAC/MacCellController/read", {},
        )
        data = resp.get("data") if isinstance(resp, dict) else None
        if isinstance(data, list):
            cells_raw = data
        elif isinstance(data, dict):
            cells_raw = data.get("cells", []) or []
        else:
            cells_raw = []
        return [
            c.get("cell_id") or c.get("name")
            for c in cells_raw if isinstance(c, dict) and (c.get("cell_id") or c.get("name"))
        ]

    # ── Cell on/off — energy saving xApp 用 ───────────────────────
    @staticmethod
    def post_cell_disable(cell_id: str) -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/MAC/MacCellController/disable", {"cell_id": cell_id},
        )

    @staticmethod
    def post_cell_enable(cell_id: str) -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/MAC/MacCellController/enable", {"cell_id": cell_id},
        )

    # ── PRB quota — xApp E2 Control Style 2 / Action 6 ───────────
    @staticmethod
    def post_set_prb_quota(cell_id: str, *, min_prb: int, max_prb: int,
                            dedicated_prb: int, set_by: str = "xApp") -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/MAC/MacScheduler/set_prb_quota",
            {"cell_id": cell_id, "min_prb": min_prb, "max_prb": max_prb,
             "dedicated_prb": dedicated_prb, "set_by": set_by},
        )

    @staticmethod
    def post_clear_prb_quota(cell_id: str) -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/MAC/MacScheduler/clear_prb_quota", {"cell_id": cell_id},
        )

    # ── Auto-bootstrap helpers — ensure DU ready when traffic profile activates
    @staticmethod
    def post_register_ue(ue_id: str, serving_cell: str,
                         sinr_db: float = 15.0, rsrp_dbm: float = -80.0) -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/Tick/TickController/register_ue",
            {"ue_id": ue_id, "serving_cell": serving_cell,
             "sinr_db": sinr_db, "rsrp_dbm": rsrp_dbm},
        )

    @staticmethod
    def post_create_rlc_entity(ue_id: str, bearer_id: int = 1) -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/RLC/RlcEntityController/create",
            {"ue_id": ue_id, "bearer_type": "DRB", "bearer_id": bearer_id, "mode": "AM"},
        )

    @staticmethod
    def post_tick_start() -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/Tick/TickController/start", {},
        )
