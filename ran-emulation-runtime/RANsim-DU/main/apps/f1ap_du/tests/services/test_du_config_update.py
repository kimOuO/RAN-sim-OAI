"""du_config_update service tests — pure logic with mocked CU client."""
from unittest.mock import patch

import pytest
from ran_sim_protocol.common import CellConfig

from main.apps.f1ap_du.services.optional.lifecycle import du_bootstrap, du_config_update


@pytest.fixture(autouse=True)
def _reset_state():
    du_bootstrap.reset_state()
    du_config_update.reset_tx_counter()
    yield
    du_bootstrap.reset_state()
    du_config_update.reset_tx_counter()


def _force_active_state() -> None:
    """直接戳 du_bootstrap 的 _done 模擬 F1 ACTIVE。"""
    du_bootstrap._done.set()


def test_tx_counter_starts_at_zero_and_monotonic():
    assert du_config_update.get_tx_counter() == 0
    a = du_config_update._next_tx_id()
    b = du_config_update._next_tx_id()
    assert a == 1 and b == 2


def test_send_skipped_when_f1_not_active():
    """F1Setup 還沒完成時 send() 應該 no-op、不打 HTTP。"""
    cell = CellConfig(cell_id="c1", pci=1, frequency_ghz=3.5, bandwidth_mhz=100.0)
    with patch(
        "main.apps.f1ap_du.services.optional.lifecycle.du_config_update."
        "CuClientBusinessService.post_du_configuration_update",
        return_value={"data": {"transaction_id": 1, "accepted": True}},
    ) as mock_post:
        result = du_config_update.send(cells_to_add=[cell])
    assert result is None
    mock_post.assert_not_called()


def test_send_no_op_when_no_changes():
    _force_active_state()
    with patch(
        "main.apps.f1ap_du.services.optional.lifecycle.du_config_update."
        "CuClientBusinessService.post_du_configuration_update",
        return_value=None,
    ) as mock_post:
        result = du_config_update.send()
    assert result is None
    mock_post.assert_not_called()


def test_send_active_state_calls_cu_with_correct_payload():
    _force_active_state()
    cell = CellConfig(cell_id="c1", pci=42, frequency_ghz=3.5, bandwidth_mhz=100.0)
    fake_resp = {"data": {"transaction_id": 1, "accepted": True}}
    with patch(
        "main.apps.f1ap_du.services.optional.lifecycle.du_config_update."
        "CuClientBusinessService.post_du_configuration_update",
        return_value=fake_resp,
    ) as mock_post:
        result = du_config_update.send(cells_to_add=[cell])
    assert result is fake_resp
    args, _ = mock_post.call_args
    payload = args[0]
    assert payload["transaction_id"] == 1
    assert len(payload["served_cells_to_add"]) == 1
    assert payload["served_cells_to_add"][0]["cell_id"] == "c1"
    assert payload["served_cells_to_modify"] == []
    assert payload["served_cells_to_delete"] == []


def test_force_bypasses_active_check():
    cell = CellConfig(cell_id="c1", pci=1, frequency_ghz=3.5, bandwidth_mhz=100.0)
    with patch(
        "main.apps.f1ap_du.services.optional.lifecycle.du_config_update."
        "CuClientBusinessService.post_du_configuration_update",
        return_value={"data": {"transaction_id": 1, "accepted": True}},
    ) as mock_post:
        result = du_config_update.send(cells_to_add=[cell], force=True)
    assert result is not None
    mock_post.assert_called_once()


def test_send_returns_none_when_cu_unreachable():
    _force_active_state()
    cell = CellConfig(cell_id="c1", pci=1, frequency_ghz=3.5, bandwidth_mhz=100.0)
    with patch(
        "main.apps.f1ap_du.services.optional.lifecycle.du_config_update."
        "CuClientBusinessService.post_du_configuration_update",
        return_value=None,
    ):
        result = du_config_update.send(cells_to_modify=[cell])
    assert result is None


def test_cell_state_to_config_maps_fields():
    """cell_state_to_config 應正確轉換 ORM → dataclass。"""
    class FakeCell:
        cell_id = "c1"
        pci = 7
        freq_ghz = 28.0
        bw_mhz = 200.0
        served_plmn = "00102"

    cfg = du_config_update.cell_state_to_config(FakeCell())
    assert cfg.cell_id == "c1"
    assert cfg.pci == 7
    assert cfg.frequency_ghz == 28.0
    assert cfg.bandwidth_mhz == 200.0
    assert cfg.served_plmn == "00102"
