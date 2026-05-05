"""NGAP procedure stubs for InitialUEMessage / InitialContextSetup.

OAI ref:
  - openair2/RRC/NR/rrc_gNB_NGAP.c (rrc_gNB_send_NGAP_NAS_FIRST_REQ at L226)
  - openair3/NGAP/ngap_gNB_handlers.c (ngap_gNB_handle_pdusession_setup_request at L921)
"""
from __future__ import annotations

from typing import Any

import requests

from main.utils.env_loader import get_int, get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)

_TIMEOUT_SEC = 5.0


def _amf_base_url() -> str:
    host = get_str("HTTP_AMF_HOST")
    port = get_str("HTTP_AMF_PORT", "8000")
    if not host:
        return ""
    return f"http://{host}:{port}"


class NgapHandler:
    @staticmethod
    def build_ng_setup_request() -> dict[str, Any]:
        return {
            "gnb_id": get_int("GNB_ID", default=57344),
            "plmn_id": get_str("PLMN_ID", "00101"),
            "served_tac": [get_int("SERVED_TAC", default=1)],
        }

    @staticmethod
    def push_initial_ue_message(payload: dict[str, Any]) -> dict[str, Any]:
        url = _amf_base_url()
        if not url:
            logger.info("AMF not configured — InitialUEMessage suppressed: %s", payload)
            return {"success": False, "skipped": True}
        try:
            resp = requests.post(
                f"{url}/api/v0.1/AMF/Ngap/AmfRouter/initial_ue_message",
                json=payload,
                timeout=_TIMEOUT_SEC,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("InitialUEMessage delivery failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def extract_pdu_sessions(initial_context_setup_payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Pull pdu_session_resources out of an InitialContextSetupRequest."""
        return list(initial_context_setup_payload.get("pdu_session_resources", []))
