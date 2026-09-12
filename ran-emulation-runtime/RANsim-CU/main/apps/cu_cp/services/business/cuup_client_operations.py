"""CU-CP → CU-UP transport (E1AP). Mirrors OAI's cucp_cuup_if_t abstraction.

OAI ref:
  - openair2/RRC/NR/cucp_cuup_if.h (function-pointer struct)
  - openair2/RRC/NR/cucp_cuup_direct.c  (integrated mode — direct call)
  - openair2/RRC/NR/cucp_cuup_e1ap.c    (split mode — SCTP/ASN.1)

Decision rule:
  - HTTP_CUUP_HOST set  → split mode → POST to CU-UP container
  - HTTP_CUUP_HOST blank → integrated mode → call cu_up.E1apHandler in-process
"""
from __future__ import annotations

from typing import Any

import requests

from main.utils.env_loader import get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)

_TIMEOUT_SEC = 5.0


def _cuup_base_url() -> str:
    host = get_str("HTTP_CUUP_HOST")
    port = get_str("HTTP_CUUP_PORT", "8000")
    if not host:
        return ""
    return f"http://{host}:{port}"


class CuupClientBusinessService:
    @staticmethod
    def is_split() -> bool:
        return bool(get_str("HTTP_CUUP_HOST"))

    @staticmethod
    def bearer_context_setup(payload: dict[str, Any]) -> dict[str, Any]:
        if CuupClientBusinessService.is_split():
            url = f"{_cuup_base_url()}/api/v0.1/CU/E1AP/E1ApRouter/bearer_context_setup"
            try:
                resp = requests.post(url, json=payload, timeout=_TIMEOUT_SEC)
                resp.raise_for_status()
                return resp.json().get("data", resp.json())
            except requests.RequestException as exc:
                logger.error("CU-UP split call failed: %s", exc)
                return {"success": False, "error": str(exc)}

        # Integrated mode — direct in-process call (mirrors cucp_cuup_direct.c).
        # Late import to avoid circular dependencies.
        from main.apps.cu_up.services.optional.e1ap.e1ap_handler import E1apHandler

        return E1apHandler.bearer_context_setup(payload)
