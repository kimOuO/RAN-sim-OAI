"""對 mock CU 驗證 UL RRC outbound 的 URL path 與 payload schema。"""
import base64
import json

import pytest
from django.test import Client

from main.apps.f1ap_du.services.optional.ul_rrc.ul_rrc_dispatcher import UlRrcDispatcher


def test_dispatch_directly_hits_cu_with_correct_url(mock_cu):
    rrc_bytes = b"\x00\x01\x02RRCSetupRequest"
    ok = UlRrcDispatcher.dispatch("ue-direct", rrc_bytes, timeout=2.0)
    assert ok is True
    assert len(mock_cu.calls) == 1
    call = mock_cu.calls[0]
    assert call["path"] == "/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message"
    body = call["payload"]
    assert body["ue_id"] == "ue-direct"
    assert base64.b64decode(body["rrc_msg_b64"]) == rrc_bytes


@pytest.mark.django_db
def test_actor_endpoint_forwards_to_mock_cu(mock_cu):
    """通過 Django endpoint 走完整路徑:Client → actor → dispatcher → mock CU。"""
    rrc_bytes = b"actor-end-to-end"
    b64 = base64.b64encode(rrc_bytes).decode()
    resp = Client().post(
        "/api/v0.1/DU/F1AP/F1ApRouter/ul_rrc_message",
        data=json.dumps({"ue_id": "ue-actor", "rrc_msg_b64": b64}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["forwarded_to_cu"] is True

    # mock CU 真的收到一筆,內容對得上
    cu_call = mock_cu.calls[0]
    assert cu_call["path"] == "/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message"
    assert cu_call["payload"]["ue_id"] == "ue-actor"
    assert base64.b64decode(cu_call["payload"]["rrc_msg_b64"]) == rrc_bytes


@pytest.mark.django_db
def test_full_attach_flow_msg1_to_msg3_via_ul_rrc(mock_cu):
    """完整 RA attach: ue_context_setup → 送 ul_rrc_message(is_initial) →
    驗證 mock CU 收到 UL RRC + RA state 進入 MSG4_SENT。"""
    client = Client()
    # 先建 UE context(會自動觸發 RA Msg1)
    client.post(
        "/api/v0.1/DU/F1AP/F1ApRouter/ue_context_setup",
        data=json.dumps({"ue_id": "ue-attach", "drbs": []}),
        content_type="application/json",
    )

    # ue_context_setup 內部已 finalize RA。為了這個測試模擬「真實 RA 流程裡 Msg3 還在 RA 中」,
    # 我們直接重新觸發 Msg1。
    from main.apps.mac.services.optional.random_access.ra_manager import get_ra_manager
    get_ra_manager().msg1_detected("ue-attach", ts_ms=1)

    rrc = b"RRCSetupRequest-from-attach"
    resp = client.post(
        "/api/v0.1/DU/F1AP/F1ApRouter/ul_rrc_message",
        data=json.dumps({
            "ue_id": "ue-attach",
            "rrc_msg_b64": base64.b64encode(rrc).decode(),
            "is_initial": True,
        }),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["forwarded_to_cu"] is True
    assert body["data"]["ra_state"] == "MSG4_SENT"

    cu_calls = mock_cu.calls_to("/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message")
    assert len(cu_calls) == 1
    assert base64.b64decode(cu_calls[0]["payload"]["rrc_msg_b64"]) == rrc


def test_dispatcher_returns_false_on_cu_unreachable(monkeypatch):
    monkeypatch.setenv("HTTP_CU_HOST", "127.0.0.1")
    monkeypatch.setenv("HTTP_CU_PORT", "1")
    assert UlRrcDispatcher.dispatch("ue-x", b"data", timeout=0.3) is False
