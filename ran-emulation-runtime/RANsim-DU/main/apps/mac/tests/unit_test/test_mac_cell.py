"""Cell endpoint smoke test — Django test client。"""
import json

import pytest
from django.test import Client


@pytest.mark.django_db
def test_cell_create_and_read():
    c = Client()
    payload = {"cell_id": "cell-test-0", "pci": 7, "total_prb": 273}
    resp = c.post(
        "/api/v0.1/DU/MAC/MacCellController/create",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code in (200, 201), resp.content
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["pci"] == 7

    resp2 = c.post(
        "/api/v0.1/DU/MAC/MacCellController/read",
        data=json.dumps({"cell_id": "cell-test-0"}),
        content_type="application/json",
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["cell_id"] == "cell-test-0"
