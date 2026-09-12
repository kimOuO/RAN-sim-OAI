"""E1 Bearer Context Setup E2E test."""
from __future__ import annotations

import json

import pytest
from django.test import Client


@pytest.mark.django_db
def test_bearer_setup_creates_drb_with_teid():
    client = Client()
    body = {
        "ue_id": "ue-002",
        "drbs": [
            {"drb_id": 1, "qos_5qi": 9, "rlc_mode": "AM"},
            {"drb_id": 2, "qos_5qi": 1, "rlc_mode": "AM"},
        ],
    }
    resp = client.post(
        "/api/v0.1/CU/E1AP/E1ApRouter/bearer_context_setup",
        data=json.dumps(body), content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] is True
    assert len(data["drb_setup_list"]) == 2
    for entry in data["drb_setup_list"]:
        assert entry["success"] is True
        assert entry["cu_up_teid"] > 0

    from main.apps.cu_up.models.drb import Drb
    assert Drb.objects.filter(ue_id="ue-002").count() == 2
