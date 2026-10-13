"""RU HTTP client — DU → RU 的 FAPI 通道。"""
from __future__ import annotations

from typing import Any

import requests

from main.utils.env_loader import get_int, get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)


class RuClientBusinessService:

    @staticmethod
    def _base_url() -> str:
        host = get_str("HTTP_RU_HOST", "ru")
        port = get_int("HTTP_RU_PORT", 8000)
        return f"http://{host}:{port}"

    # 2026-09-22:RU 的 dl/ul_tti 回應本體就帶了 cqi/crc_indications,直接在這裡套用,
    # 不再靠 RU 逐 UE 打 HTTP 回 DU(那條回呼是 RU↔DU 互等、假 RLF 的來源)。
    # 連線改用 Session 重用,不再每 tick 開新 TCP。
    _session = None

    @staticmethod
    def _sess():
        if RuClientBusinessService._session is None:
            RuClientBusinessService._session = requests.Session()
        return RuClientBusinessService._session

    @staticmethod
    def _post_tti(path: str, payload: dict[str, Any], timeout: float, kind: str) -> bool:
        url = f"{RuClientBusinessService._base_url()}/api/v0.1/RU/FAPI/FapiRouter/{path}"
        try:
            r = RuClientBusinessService._sess().post(url, json=payload, timeout=timeout)
        except requests.RequestException as e:
            logger.warning("post_%s failed: %s", path, e)
            return False
        if not r.ok:
            return False
        try:
            from main.apps.fapi_north.services.business.indication_apply import apply_from_response
            apply_from_response(r.json(), kind)
        except Exception:  # noqa: BLE001 — 套用失敗不該讓 tick 以為 RU 沒回
            logger.exception("%s 回應本體套用失敗", path)
        return True

    @staticmethod
    def post_dl_tti_request(payload: dict[str, Any], timeout: float = 1.0) -> bool:
        return RuClientBusinessService._post_tti("dl_tti_request", payload, timeout, "cqi")

    @staticmethod
    def post_ul_tti_request(payload: dict[str, Any], timeout: float = 1.0) -> bool:
        return RuClientBusinessService._post_tti("ul_tti_request", payload, timeout, "crc")

    @staticmethod
    def post_beam_control(payload: dict[str, Any], timeout: float = 5.0) -> dict[str, Any]:
        """B2(2026-09-16):把 RIC 的波束控制轉給 RU(電子下傾 / GoB 子集 / 最大層數)。"""
        import requests
        url = f"{RuClientBusinessService._base_url()}/api/v0.1/RU/Config/BeamController/set"
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            body = r.json() if r.content else {}
            return {"ok": r.status_code == 200, "status": r.status_code, "body": body}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "status": 0, "error": str(exc)}

    @staticmethod
    def post_cell_active(cell_id: str, active: bool, timeout: float = 3.0) -> dict[str, Any]:
        """2026-10-13:DU 開 / 關 cell 時同步 RU 的發射開關。

        以前只有劇本預排的關站事件會同時切 DU 與 RU;RIC 節能(CU → DU disable)與手動鎖定
        只停了 DU 排程,RU 照樣發射 —— UE 仍量得到已關的 cell(常是最強),A3 不斷觸發往它換手
        而失敗(S3 實測:鎖 4 分鐘失敗 45 次、節能 6 分鐘失敗 77 次)。"""
        url = f"{RuClientBusinessService._base_url()}/api/v0.1/RU/Config/RuController/set_cell_active"
        try:
            r = requests.post(url, json={"cell_id": cell_id, "is_active": bool(active)}, timeout=timeout)
            body = r.json() if r.content else {}
            return {"ok": r.status_code == 200, "status": r.status_code, "body": body}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "status": 0, "error": str(exc)}
