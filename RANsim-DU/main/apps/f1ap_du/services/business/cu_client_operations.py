"""CU HTTP client — 包 requests,讀 HTTP_CU_HOST/PORT。

對齊 OAI 的 f1ap_itti_send_sctp_data_req(我們用 HTTP POST 取代 SCTP)。
"""
from __future__ import annotations

from typing import Any

import requests

from main.utils.env_loader import get_int, get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)


class CuClientBusinessService:
    """單例風格:每次 call 重建 client(無連線池);適合低頻 control plane。"""

    @staticmethod
    def _base_url() -> str:
        host = get_str("HTTP_CU_HOST", "cu")
        port = get_int("HTTP_CU_PORT", 8000)
        return f"http://{host}:{port}"

    @staticmethod
    def post_du_setup(payload: dict[str, Any], timeout: float = 5.0) -> dict[str, Any] | None:
        url = f"{CuClientBusinessService._base_url()}/api/v0.1/CU/F1AP/F1ApRouter/du_setup"
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            return r.json() if r.ok else None
        except requests.RequestException as e:
            logger.warning("post_du_setup failed: %s", e)
            return None

    @staticmethod
    def post_measurement_report(payload: dict[str, Any], timeout: float = 5.0) -> bool:
        url = f"{CuClientBusinessService._base_url()}/api/v0.1/CU/F1AP/F1ApRouter/measurement_report"
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            return r.ok
        except requests.RequestException as e:
            logger.warning("post_measurement_report failed: %s", e)
            return False

    @staticmethod
    def post_ul_rrc_message(payload: dict[str, Any], timeout: float = 5.0) -> bool:
        url = f"{CuClientBusinessService._base_url()}/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message"
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            return r.ok
        except requests.RequestException as e:
            logger.warning("post_ul_rrc_message failed: %s", e)
            return False
