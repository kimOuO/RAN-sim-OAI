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

    @staticmethod
    def post_dl_tti_request(payload: dict[str, Any], timeout: float = 1.0) -> bool:
        url = f"{RuClientBusinessService._base_url()}/api/v0.1/RU/FAPI/FapiRouter/dl_tti_request"
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            return r.ok
        except requests.RequestException as e:
            logger.warning("post_dl_tti_request failed: %s", e)
            return False

    @staticmethod
    def post_ul_tti_request(payload: dict[str, Any], timeout: float = 1.0) -> bool:
        url = f"{RuClientBusinessService._base_url()}/api/v0.1/RU/FAPI/FapiRouter/ul_tti_request"
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            return r.ok
        except requests.RequestException as e:
            logger.warning("post_ul_tti_request failed: %s", e)
            return False
