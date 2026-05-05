import json

import pytest
from django.test import Client


@pytest.mark.django_db
def test_cqi_indication_returns_new_mcs():
    c = Client()
    payload = {"ue_id": "ue-cqi-1", "sinr_db": 20.0, "cqi": 12, "rank": 1, "pmi": 0}
    resp = c.post(
        "/api/v0.1/DU/FAPI/FapiRouter/cqi_indication",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["ue_id"] == "ue-cqi-1"
    assert "new_mcs" in body["data"]


@pytest.mark.django_db
def test_crc_indication_unknown_ue_returns_unknown():
    c = Client()
    payload = {"ue_id": "ue-noexist", "harq_pid": 0, "success": True}
    resp = c.post(
        "/api/v0.1/DU/FAPI/FapiRouter/crc_indication",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
