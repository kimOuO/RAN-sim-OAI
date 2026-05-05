"""對 mock CU 驗證 gNB-DU Configuration Update outbound。

涵蓋:
  1. F1 inactive → MacCellController.create 不送 config update(只 F1Setup 會帶)
  2. F1 active → create 送 add 通知,update 送 modify 通知,URL 對 / payload 結構正確
  3. transaction_id 單調遞增
  4. CU 不可達 → service 回 None,不擋 actor flow
"""
import json

import pytest
from django.test import Client

from main.apps.f1ap_du.services.optional.lifecycle import du_bootstrap, du_config_update


def _force_active() -> None:
    du_bootstrap._done.set()


def _post(client: Client, url: str, body: dict) -> dict:
    resp = client.post(url, data=json.dumps(body), content_type="application/json")
    assert resp.status_code in (200, 201), f"{url} → {resp.status_code} {resp.content!r}"
    return resp.json()


@pytest.mark.django_db
def test_create_cell_when_f1_inactive_does_not_call_cu(mock_cu):
    """F1Setup 還沒完成時新增 cell — 不該打 CU(F1Setup 會帶 served_cells)。"""
    body = _post(
        Client(), "/api/v0.1/DU/MAC/MacCellController/create",
        {"cell_id": "cell-A", "pci": 1, "total_prb": 100},
    )
    assert body["data"]["pci"] == 1
    cu_calls = mock_cu.calls_to("/api/v0.1/CU/F1AP/F1ApRouter/du_configuration_update")
    assert len(cu_calls) == 0


@pytest.mark.django_db
def test_create_cell_when_f1_active_sends_add_to_cu(mock_cu):
    _force_active()
    _post(
        Client(), "/api/v0.1/DU/MAC/MacCellController/create",
        {"cell_id": "cell-B", "pci": 2, "total_prb": 100, "freq_ghz": 3.5},
    )

    cu_calls = mock_cu.calls_to("/api/v0.1/CU/F1AP/F1ApRouter/du_configuration_update")
    assert len(cu_calls) == 1
    payload = cu_calls[0]["payload"]
    assert "gnb_du_id" in payload
    assert payload["transaction_id"] == 1
    assert len(payload["served_cells_to_add"]) == 1
    cell = payload["served_cells_to_add"][0]
    assert cell["cell_id"] == "cell-B"
    assert cell["pci"] == 2
    assert payload["served_cells_to_modify"] == []
    assert payload["served_cells_to_delete"] == []


@pytest.mark.django_db
def test_recreate_existing_cell_sends_modify_not_add(mock_cu):
    """同 cell_id 第二次 create 視為 update,送 modify 而非 add。"""
    _force_active()
    c = Client()
    _post(c, "/api/v0.1/DU/MAC/MacCellController/create",
          {"cell_id": "cell-C", "pci": 3, "total_prb": 100})
    _post(c, "/api/v0.1/DU/MAC/MacCellController/create",
          {"cell_id": "cell-C", "pci": 3, "total_prb": 273})  # 改 prb

    cu_calls = mock_cu.calls_to("/api/v0.1/CU/F1AP/F1ApRouter/du_configuration_update")
    assert len(cu_calls) == 2
    # 第一次 create -> add
    assert len(cu_calls[0]["payload"]["served_cells_to_add"]) == 1
    assert cu_calls[0]["payload"]["transaction_id"] == 1
    # 第二次 create(已存在)-> modify
    assert len(cu_calls[1]["payload"]["served_cells_to_modify"]) == 1
    assert cu_calls[1]["payload"]["transaction_id"] == 2


@pytest.mark.django_db
def test_update_cell_sends_modify_to_cu(mock_cu):
    _force_active()
    c = Client()
    _post(c, "/api/v0.1/DU/MAC/MacCellController/create",
          {"cell_id": "cell-D", "pci": 4, "total_prb": 100})
    # update via update endpoint
    _post(c, "/api/v0.1/DU/MAC/MacCellController/update",
          {"cell_id": "cell-D", "pci": 5})

    cu_calls = mock_cu.calls_to("/api/v0.1/CU/F1AP/F1ApRouter/du_configuration_update")
    # create -> add, update -> modify
    assert len(cu_calls) == 2
    second_payload = cu_calls[1]["payload"]
    assert len(second_payload["served_cells_to_modify"]) == 1
    assert second_payload["served_cells_to_modify"][0]["pci"] == 5


@pytest.mark.django_db
def test_transaction_id_monotonic_across_changes(mock_cu):
    _force_active()
    c = Client()
    for i in range(3):
        _post(c, "/api/v0.1/DU/MAC/MacCellController/create",
              {"cell_id": f"cell-T{i}", "pci": i, "total_prb": 100})
    cu_calls = mock_cu.calls_to("/api/v0.1/CU/F1AP/F1ApRouter/du_configuration_update")
    tids = [c["payload"]["transaction_id"] for c in cu_calls]
    assert tids == [1, 2, 3]


@pytest.mark.django_db
def test_cu_unreachable_does_not_break_actor_flow(monkeypatch):
    """CU port 1 不通 — actor 仍應成功(create cell 不該因 CU 通知失敗 rollback)。"""
    _force_active()
    monkeypatch.setenv("HTTP_CU_HOST", "127.0.0.1")
    monkeypatch.setenv("HTTP_CU_PORT", "1")

    body = _post(
        Client(), "/api/v0.1/DU/MAC/MacCellController/create",
        {"cell_id": "cell-unreach", "pci": 9, "total_prb": 100},
    )
    assert body["data"]["pci"] == 9


@pytest.mark.django_db
def test_send_directly_against_mock_cu_returns_ack_body(mock_cu):
    """直接呼叫 service.send(force=True) 跳過 active check,驗證 ACK 路徑。"""
    from ran_sim_protocol.common import CellConfig
    cell = CellConfig(cell_id="c-direct", pci=99, frequency_ghz=3.5, bandwidth_mhz=100.0)
    resp = du_config_update.send(cells_to_add=[cell], force=True, timeout=2.0)
    assert resp is not None
    cu_calls = mock_cu.calls_to("/api/v0.1/CU/F1AP/F1ApRouter/du_configuration_update")
    assert len(cu_calls) == 1
    assert cu_calls[0]["payload"]["served_cells_to_add"][0]["cell_id"] == "c-direct"
