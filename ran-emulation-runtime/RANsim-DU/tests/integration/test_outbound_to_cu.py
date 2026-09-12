"""驗證 DU 發給 CU 的訊息(URL path / payload schema)正確。"""
from __future__ import annotations

import pytest
from ran_sim_protocol.f1ap import GnbDuMeasurementReport

from main.apps.f1ap_du.services.business.cu_client_operations import CuClientBusinessService
from main.apps.f1ap_du.services.optional.lifecycle.du_bootstrap import _build_setup_message
from main.apps.f1ap_du.services.optional.message_codec.f1ap_codec import (
    encode_f1_setup,
    encode_measurement_report,
)


@pytest.mark.django_db
def test_du_setup_hits_cu_with_correct_url_and_schema(mock_cu):
    msg = _build_setup_message()
    payload = encode_f1_setup(msg)

    resp = CuClientBusinessService.post_du_setup(payload, timeout=2.0)

    assert resp is not None, "CU mock should respond, post_du_setup got None"
    assert len(mock_cu.calls) == 1
    call = mock_cu.calls[0]
    assert call["path"] == "/api/v0.1/CU/F1AP/F1ApRouter/du_setup"
    body = call["payload"]
    assert "gnb_du_id" in body
    assert "served_cells" in body
    assert isinstance(body["served_cells"], list)
    assert len(body["served_cells"]) >= 1
    cell = body["served_cells"][0]
    assert {"cell_id", "pci", "frequency_ghz", "bandwidth_mhz", "served_plmn"} <= set(cell.keys())


def test_measurement_report_hits_cu_with_correct_url_and_schema(mock_cu):
    msg = GnbDuMeasurementReport(
        ue_id="ue-x",
        rsrp_dbm=-80.0,
        sinr_db=15.0,
        throughput_dl_mbps=120.0,
        throughput_ul_mbps=24.0,
        mcs_dl=18,
        rb_width_dl=100,
        mimo_rank=2,
    )
    ok = CuClientBusinessService.post_measurement_report(encode_measurement_report(msg), timeout=2.0)

    assert ok is True
    assert len(mock_cu.calls) == 1
    call = mock_cu.calls[0]
    assert call["path"] == "/api/v0.1/CU/F1AP/F1ApRouter/measurement_report"
    body = call["payload"]
    assert body["ue_id"] == "ue-x"
    assert body["rsrp_dbm"] == -80.0
    assert body["sinr_db"] == 15.0
    assert body["mcs_dl"] == 18
    assert body["mimo_rank"] == 2
    assert body["rb_width_dl"] == 100


def test_cu_unreachable_returns_none_or_false(monkeypatch):
    """指向不存在的 port 時 client 應該優雅回傳 None / False,不拋例外。"""
    monkeypatch.setenv("HTTP_CU_HOST", "127.0.0.1")
    monkeypatch.setenv("HTTP_CU_PORT", "1")  # nothing listens on port 1
    assert CuClientBusinessService.post_du_setup({"gnb_du_id": 1}, timeout=0.3) is None
    assert CuClientBusinessService.post_measurement_report({"ue_id": "x"}, timeout=0.3) is False
