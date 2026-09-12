"""UE context setup endpoint test。"""
import json

import pytest
from django.test import Client


@pytest.mark.django_db
def test_ue_context_setup_creates_state_and_drbs():
    c = Client()
    payload = {
        "ue_id": "ue-99",
        "drbs": [{"drb_id": 1, "qos_5qi": 9, "rlc_mode": "AM"}],
        "rrc_message_b64": "",
    }
    resp = c.post(
        "/api/v0.1/DU/F1AP/F1ApRouter/ue_context_setup",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code in (200, 201), resp.content
    body = resp.json()
    assert body["data"]["success"] is True
    assert 1 in body["data"]["drb_setup_list"]


@pytest.mark.django_db
def test_ue_context_release_cleans_up():
    c = Client()
    c.post(
        "/api/v0.1/DU/F1AP/F1ApRouter/ue_context_setup",
        data=json.dumps({"ue_id": "ue-77", "drbs": []}),
        content_type="application/json",
    )
    resp = c.post(
        "/api/v0.1/DU/F1AP/F1ApRouter/ue_context_release",
        data=json.dumps({"ue_id": "ue-77"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
