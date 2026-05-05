"""update_antenna actor smoke：DRF Client 走完整 request chain。"""
import json

import pytest
from rest_framework.test import APIClient

from main.apps.antenna.models.antenna_config import AntennaConfig


@pytest.mark.django_db
def test_update_antenna_creates_row():
    client = APIClient()
    payload = {
        "rows": 4,
        "cols": 2,
        "polarization": "cross",
        "pattern": "tr38901",
    }
    resp = client.post(
        "/api/v0.1/RU/Config/RuController/update_antenna",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["rows"] == 4
    assert body["data"]["polarization"] == "cross"
    assert AntennaConfig.objects.count() == 1


@pytest.mark.django_db
def test_update_antenna_validation_fails_on_bad_pattern():
    client = APIClient()
    payload = {"rows": 4, "cols": 2, "polarization": "cross", "pattern": "garbage"}
    resp = client.post(
        "/api/v0.1/RU/Config/RuController/update_antenna",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 400
