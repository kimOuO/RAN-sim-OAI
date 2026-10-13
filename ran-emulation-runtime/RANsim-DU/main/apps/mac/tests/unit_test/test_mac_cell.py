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


@pytest.mark.django_db
def test_disable_enable_syncs_ru_transmit():
    """2026-10-13:DU 關 / 開 cell 時要同步 RU 發射開關(否則 UE 仍量得到已關的 cell)。"""
    from unittest.mock import patch
    c = Client()
    c.post("/api/v0.1/DU/MAC/MacCellController/create",
           data=json.dumps({"cell_id": "cell-ru-0", "pci": 3, "total_prb": 106}), content_type="application/json")
    calls = []
    with patch("main.apps.fapi_north.services.business.ru_client_operations.RuClientBusinessService.post_cell_active",
               side_effect=lambda cid, act, **_: calls.append((cid, act)) or {"ok": True}), \
         patch("main.apps.f1ap_du.services.optional.lifecycle.du_config_update.send"):
        r1 = c.post("/api/v0.1/DU/MAC/MacCellController/disable", data=json.dumps({"cell_id": "cell-ru-0"}),
                    content_type="application/json")
        r2 = c.post("/api/v0.1/DU/MAC/MacCellController/enable", data=json.dumps({"cell_id": "cell-ru-0"}),
                    content_type="application/json")
    assert r1.status_code == 200 and r2.status_code == 200
    assert calls == [("cell-ru-0", False), ("cell-ru-0", True)]


@pytest.mark.django_db
def test_disable_still_succeeds_when_ru_unreachable():
    """RU 失敗只記警告,DU 的關 cell 仍要成功(DU 排程狀態才是服務與否的依據)。"""
    from unittest.mock import patch
    c = Client()
    c.post("/api/v0.1/DU/MAC/MacCellController/create",
           data=json.dumps({"cell_id": "cell-ru-1", "pci": 4, "total_prb": 106}), content_type="application/json")
    with patch("main.apps.fapi_north.services.business.ru_client_operations.RuClientBusinessService.post_cell_active",
               return_value={"ok": False, "status": 0, "error": "unreachable"}), \
         patch("main.apps.f1ap_du.services.optional.lifecycle.du_config_update.send"):
        r = c.post("/api/v0.1/DU/MAC/MacCellController/disable", data=json.dumps({"cell_id": "cell-ru-1"}),
                   content_type="application/json")
    assert r.status_code == 200 and r.json()["data"]["is_active"] is False
