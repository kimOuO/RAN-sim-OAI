import json

import pytest
from django.test import Client

from main.apps.tick.services.optional.runner.tick_runner import _singleton  # noqa: F401


@pytest.mark.django_db
def test_run_once_returns_status():
    c = Client()
    resp = c.post("/api/v0.1/DU/Tick/TickController/run_once", data="{}", content_type="application/json")
    assert resp.status_code == 200
    body = resp.json()
    assert "tick_count" in body["data"]


@pytest.mark.django_db
def test_register_then_read():
    c = Client()
    c.post(
        "/api/v0.1/DU/Tick/TickController/register_ue",
        data=json.dumps({"ue_id": "ue-tick-1", "serving_cell": "cell-0"}),
        content_type="application/json",
    )
    resp = c.post("/api/v0.1/DU/Tick/TickController/read", data="{}", content_type="application/json")
    assert resp.status_code == 200
