"""NGAP procedure stubs for InitialUEMessage / InitialContextSetup.

OAI ref:
  - openair2/RRC/NR/rrc_gNB_NGAP.c (rrc_gNB_send_NGAP_NAS_FIRST_REQ at L226)
  - openair3/NGAP/ngap_gNB_handlers.c (ngap_gNB_handle_pdusession_setup_request at L921)

當 HTTP_AMF_HOST 未設（沒接真 5GC），啟用 mock AMF 自響應：
  RRC SetupComplete → CU 發 InitialUEMessage（被 mock AMF 接走）
  Mock AMF 立刻回 InitialContextSetup → CU 自己 NGAP receiver 處理
這樣 NGAP 訊息流量會在 RAN message log 出現，sim 看起來更完整。
"""
from __future__ import annotations

import threading
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


def _mock_amf_respond_initial_context_setup(initial_ue_payload: dict[str, Any]) -> None:
    """Mock AMF 對 InitialUEMessage 自動回 InitialContextSetup。

    模擬 5GC AMF rubber-stamp（OAI 開源 AMF 也是接受 by default）。
    POST 到 CU 自己的 NGAP receiver endpoint 走完整 HTTP 路徑（log middleware 才看得到）。
    用 thread 非同步發送，避免阻塞 RRC SetupComplete handler。
    """
    ran_ue_ngap_id = initial_ue_payload.get("ran_ue_ngap_id")
    if not ran_ue_ngap_id:
        return

    payload = {
        "ran_ue_ngap_id": ran_ue_ngap_id,
        "amf_ue_ngap_id": int(ran_ue_ngap_id) + 1,    # 跟 RRC attach 時生成的 amf_ue_ngap_id 對齊
        "pdu_session_resources": [
            {
                "pdu_session_id": 1,
                "qos_flow_5qi": [9],   # default 5QI=9 (best-effort)
                "ul_tunnel": {"teid": 1, "transport_layer_address": "127.0.0.1"},
                "dl_tunnel": {"teid": 2, "transport_layer_address": "127.0.0.1"},
            }
        ],
    }

    cu_self_url = "http://localhost:8000/api/v0.1/CU/NGAP/NgapRouter/initial_context_setup"
    try:
        resp = requests.post(cu_self_url, json=payload, timeout=_TIMEOUT_SEC)
        if resp.ok:
            logger.info("Mock AMF: InitialContextSetup → CU OK (ran_ue_ngap_id=%s)", ran_ue_ngap_id)
        else:
            logger.warning("Mock AMF: ICS → CU non-2xx %d %s", resp.status_code, resp.text[:200])
    except requests.RequestException as exc:
        logger.warning("Mock AMF self-respond failed: %s", exc)


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
            # 沒真 AMF — 啟動 mock AMF 自響應
            logger.info("InitialUEMessage (no AMF) → triggering mock AMF self-respond: %s", payload)
            t = threading.Thread(
                target=_mock_amf_respond_initial_context_setup,
                args=(payload,),
                daemon=True,
            )
            t.start()
            return {"success": True, "mock_amf": True}
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
