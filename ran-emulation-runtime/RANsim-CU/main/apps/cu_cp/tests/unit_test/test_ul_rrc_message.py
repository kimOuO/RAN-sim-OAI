"""UL RRC message → CONNECTED transition end-to-end."""
from __future__ import annotations

import json

import pytest
from django.test import Client

from main.apps.cu_cp.services.optional.rrc.message_handler import (
    RrcMessageHandler, RrcMessageType,
)


@pytest.mark.django_db
def test_setup_request_then_complete_reaches_connected():
    client = Client()

    # 1) UE sends RRCSetupRequest — first contact creates UE in IDLE → SETUP
    setup_req = RrcMessageHandler.encode(RrcMessageType.SETUP_REQUEST, {})
    r1 = client.post(
        "/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message",
        data=json.dumps({"ue_id": "ue-001", "rrc_msg_b64": setup_req}),
        content_type="application/json",
    )
    assert r1.status_code == 200
    assert r1.json()["data"]["next_state"] == "SETUP"

    # 2) UE responds RRCSetupComplete — SETUP → CONNECTED
    setup_complete = RrcMessageHandler.encode(
        RrcMessageType.SETUP_COMPLETE, {"nas_pdu_b64": ""},
    )
    r2 = client.post(
        "/api/v0.1/CU/F1AP/F1ApRouter/ul_rrc_message",
        data=json.dumps({"ue_id": "ue-001", "rrc_msg_b64": setup_complete}),
        content_type="application/json",
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["next_state"] == "CONNECTED"

    from main.apps.cu_cp.models.ue_context import UeContext
    ue = UeContext.objects.get(ue_id="ue-001")
    assert ue.rrc_state == "CONNECTED"
