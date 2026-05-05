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
