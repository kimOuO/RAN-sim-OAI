"""ul_rrc_message endpoint — actor 行為驗證(mock 掉 CU client)。"""
import base64
import json
from unittest.mock import patch

import pytest
from django.test import Client

from main.apps.mac.services.optional.random_access.ra_manager import get_ra_manager


def _post(client: Client, body: dict) -> tuple[int, dict]:
    resp = client.post(
        "/api/v0.1/DU/F1AP/F1ApRouter/ul_rrc_message",
        data=json.dumps(body),
        content_type="application/json",
    )
    return resp.status_code, resp.json()


@pytest.mark.django_db
def test_validation_rejects_missing_ue_id():
    code, body = _post(Client(), {"rrc_msg_b64": "AAAA"})
    assert code == 400
    assert body["status"] == "error"


@pytest.mark.django_db
def test_validation_rejects_empty_b64():
    code, body = _post(Client(), {"ue_id": "ue-1", "rrc_msg_b64": ""})
    assert code == 400


@pytest.mark.django_db
def test_invalid_b64_returns_400():
    code, body = _post(Client(), {"ue_id": "ue-1", "rrc_msg_b64": "@@@invalid"})
    assert code == 400
    assert "Bad rrc_msg_b64" in body["message"]


@pytest.mark.django_db
def test_forwards_to_cu_via_dispatcher():
    rrc_bytes = b"hello-rrc"
    b64 = base64.b64encode(rrc_bytes).decode()
    with patch(
        "main.apps.f1ap_du.services.optional.ul_rrc.ul_rrc_dispatcher.CuClientBusinessService.post_ul_rrc_message",
        return_value=True,
    ) as mock_post:
        code, body = _post(Client(), {"ue_id": "ue-99", "rrc_msg_b64": b64})
    assert code == 200
    assert body["data"]["forwarded_to_cu"] is True
    assert body["data"]["ue_id"] == "ue-99"
    # 確認 CU client 真的被呼叫,payload 一致
    payload = mock_post.call_args[0][0]
    assert payload["ue_id"] == "ue-99"
    assert payload["rrc_msg_b64"] == b64


@pytest.mark.django_db
def test_is_initial_advances_ra_state():
    """is_initial=True 應該把 RA state 推進到 MSG4_SENT。"""
    ra = get_ra_manager()
    ra.reset()
    ra.msg1_detected("ue-ra", ts_ms=1000)
    with patch(
        "main.apps.f1ap_du.services.optional.ul_rrc.ul_rrc_dispatcher.CuClientBusinessService.post_ul_rrc_message",
        return_value=True,
    ):
        code, body = _post(
            Client(),
            {"ue_id": "ue-ra", "rrc_msg_b64": base64.b64encode(b"msg3").decode(), "is_initial": True},
        )
    assert code == 200
    assert body["data"]["ra_state"] == "MSG4_SENT"


@pytest.mark.django_db
def test_non_initial_does_not_touch_ra():
    ra = get_ra_manager()
    ra.reset()
    with patch(
        "main.apps.f1ap_du.services.optional.ul_rrc.ul_rrc_dispatcher.CuClientBusinessService.post_ul_rrc_message",
        return_value=True,
    ):
        code, body = _post(
            Client(),
            {"ue_id": "ue-noRA", "rrc_msg_b64": base64.b64encode(b"reconfig").decode()},
        )
    assert code == 200
    assert body["data"]["ra_state"] is None
