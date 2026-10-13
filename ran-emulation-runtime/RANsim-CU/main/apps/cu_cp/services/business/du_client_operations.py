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
    """舊的單一 DU 端點(env HTTP_DU_HOST)。多 DU 時只在 DU 沒報端點時退回用。"""
    host = get_str("HTTP_DU_HOST")
    port = get_str("HTTP_DU_PORT", "8000")
    scheme = get_str("HTTP_DU_SCHEME", "http")
    if not host:
        return ""
    return f"{scheme}://{host}:{port}"


def endpoint_for_du(gnb_du_id: int | None) -> str:
    """gNB-DU ID → F1 端點(F1 Setup 時 DU 報上來的);查不到退回 env。"""
    if gnb_du_id is not None:
        from main.apps.cu_cp.models.du_registry import DuRegistry
        ep = DuRegistry.objects.filter(gnb_du_id=gnb_du_id).values_list("endpoint", flat=True).first()
        if ep:
            return ep
    return _du_base_url()


def du_of_cell(cell_id: str) -> int | None:
    if not cell_id:
        return None
    from main.apps.cu_cp.models.cell_config import CellConfig
    return CellConfig.objects.filter(cell_id=cell_id).values_list("served_by_du_id", flat=True).first()


def du_of_ue(ue_id: str) -> int | None:
    """UE 目前所在的 DU:UeContext.gnb_du_id(Initial UL RRC / 換手時寫入),沒有就看服務 cell。"""
    if not ue_id:
        return None
    from main.apps.cu_cp.models.ue_context import UeContext
    row = UeContext.objects.filter(ue_id=ue_id).values("gnb_du_id", "serving_cell").first()
    if not row:
        return None
    if row["gnb_du_id"] is not None:
        return int(row["gnb_du_id"])
    return du_of_cell(row["serving_cell"] or "")


def all_du_endpoints() -> list[str]:
    from main.apps.cu_cp.models.du_registry import DuRegistry
    eps = [e for e in DuRegistry.objects.values_list("endpoint", flat=True) if e]
    if eps:
        return list(dict.fromkeys(eps))
    base = _du_base_url()
    return [base] if base else []


def _resolve(payload: dict[str, Any], *, gnb_du_id: int | None = None, cell_id: str | None = None,
             ue_id: str | None = None) -> str:
    """決定 F1 訊息送哪個 DU:明指的 DU > cell 所屬 DU > UE 所在 DU > 唯一的 DU / env。"""
    if gnb_du_id is not None:
        return endpoint_for_du(gnb_du_id)
    cell = cell_id or payload.get("serving_cell_id") or payload.get("target_cell") or payload.get("cell_id")
    du = du_of_cell(cell) if cell else None
    if du is None:
        du = du_of_ue(ue_id or payload.get("ue_id") or "")
    return endpoint_for_du(du)


def du_ok(resp: Any) -> bool:
    """DU 回應是否成功。DU 的格式是 {"status": "success", ...};失敗時本 client 回 {"success": False, ...}。"""
    return isinstance(resp, dict) and (resp.get("status") == "success" or resp.get("success") is True)


class DuClientBusinessService:
    """Issue HTTP POST to the DU's F1AP router(多 DU 時依 UE / cell 路由)。"""

    @staticmethod
    def _post(path: str, payload: dict[str, Any], *, gnb_du_id: int | None = None,
              cell_id: str | None = None, ue_id: str | None = None, base: str | None = None) -> dict[str, Any]:
        base = base or _resolve(payload, gnb_du_id=gnb_du_id, cell_id=cell_id, ue_id=ue_id)
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
    def post_ue_context_setup(payload: dict[str, Any], *, gnb_du_id: int | None = None) -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/F1AP/F1ApRouter/ue_context_setup", payload, gnb_du_id=gnb_du_id,
        )

    @staticmethod
    def post_ue_context_modification(payload: dict[str, Any]) -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/F1AP/F1ApRouter/ue_context_modification", payload,
        )

    @staticmethod
    def post_ue_context_release(payload: dict[str, Any], *, gnb_du_id: int | None = None) -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/F1AP/F1ApRouter/ue_context_release", payload, gnb_du_id=gnb_du_id,
        )

    @staticmethod
    def read_mac_cells() -> list[str]:
        """讀所有 DU 當前的 cell 清單(聯集),回 cell_id list。
        AK12: release_stale 用來檢查 UeContext.serving_cell 是不是 orphan（指到
        已經不存在的 cell）。空 list 表示讀不到 — 呼叫端應該降級處理。"""
        out: list[str] = []
        for base in all_du_endpoints():
            resp = DuClientBusinessService._post("/api/v0.1/DU/MAC/MacCellController/read", {}, base=base)
            data = resp.get("data") if isinstance(resp, dict) else None
            if isinstance(data, list):
                cells_raw = data
            elif isinstance(data, dict):
                cells_raw = data.get("cells", []) or []
            else:
                cells_raw = []
            out.extend(c.get("cell_id") or c.get("name")
                       for c in cells_raw if isinstance(c, dict) and (c.get("cell_id") or c.get("name")))
        return out

    # ── Cell on/off — energy saving xApp 用 ───────────────────────
    @staticmethod
    def post_cell_disable(cell_id: str) -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/MAC/MacCellController/disable", {"cell_id": cell_id},
        )

    @staticmethod
    def post_beam_control(payload: dict[str, Any]) -> dict[str, Any]:
        """B2(2026-09-16):RC (2,8) 波束控制 → DU → RU。"""
        return DuClientBusinessService._post(
            "/api/v0.1/DU/MAC/MacCellController/set_beam_control", payload,
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
             "sinr_db": sinr_db, "rsrp_dbm": rsrp_dbm}, cell_id=serving_cell,
        )

    @staticmethod
    def post_create_rlc_entity(ue_id: str, bearer_id: int = 1) -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/RLC/RlcEntityController/create",
            {"ue_id": ue_id, "bearer_type": "DRB", "bearer_id": bearer_id, "mode": "AM"},
        )

    @staticmethod
    def post_tick_start(ue_id: str | None = None) -> dict[str, Any]:
        return DuClientBusinessService._post(
            "/api/v0.1/DU/Tick/TickController/start", {}, ue_id=ue_id,
        )
