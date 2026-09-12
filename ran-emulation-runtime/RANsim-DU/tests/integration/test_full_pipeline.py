"""End-to-end 整合 — 模擬 CU 配 UE → RU 上報 CQI → tick 跑流程 →
mock CU 收 measurement_report,mock RU 收 DlTtiRequest。
"""
from __future__ import annotations

import json

import pytest
from django.test import Client

from main.apps.rlc.services.optional.entities import factory as rlc_factory
from main.apps.tick.services.optional.runner.tick_runner import get_tick_runner


def _post(client: Client, url: str, body: dict) -> dict:
    resp = client.post(url, data=json.dumps(body), content_type="application/json")
    assert resp.status_code in (200, 201), f"{url} → {resp.status_code} body={resp.content!r}"
    return resp.json()


@pytest.mark.django_db
def test_full_loop_cu_to_du_to_ru_back_to_cu(mock_cu, mock_ru):
    client = Client()

    # 1) (CU 模擬) 對 DU 配一個 UE + 1 條 DRB(AM)
    setup_resp = _post(
        client,
        "/api/v0.1/DU/F1AP/F1ApRouter/ue_context_setup",
        {"ue_id": "ue-itest", "drbs": [{"drb_id": 1, "qos_5qi": 9, "rlc_mode": "AM"}]},
    )
    assert setup_resp["data"]["success"] is True
    assert 1 in setup_resp["data"]["drb_setup_list"]

    # 2) 把 UE 註冊進 tick registry(指明 serving cell + 初始 SINR)
    _post(
        client,
        "/api/v0.1/DU/Tick/TickController/register_ue",
        {"ue_id": "ue-itest", "serving_cell": "cell-0", "sinr_db": 18.0, "rsrp_dbm": -82.0},
    )

    # 3) (RU 模擬) 上報一筆 CQI ind — 推 MCS controller
    cqi_resp = _post(
        client,
        "/api/v0.1/DU/FAPI/FapiRouter/cqi_indication",
        {"ue_id": "ue-itest", "sinr_db": 18.0, "cqi": 11, "rank": 1, "pmi": 0},
    )
    assert cqi_resp["data"]["ue_id"] == "ue-itest"

    # 4) 模擬 F1-U 進來:灌 SDU 進 DRB,讓 BO > 0
    inject_resp = _post(
        client,
        "/api/v0.1/DU/RLC/RlcDataController/inject_sdu",
        {"ue_id": "ue-itest", "bearer_type": "DRB", "bearer_id": 1, "sdu_bytes": 5000},
    )
    assert inject_resp["data"]["bo"] > 0

    # 5) 跑 5 個 tick — 第 5 tick 應觸發 measurement_report
    runner = get_tick_runner()
    last_result = None
    for _ in range(5):
        last_result = runner.run_once()

    assert last_result["scheduled_ues"] == ["ue-itest"]
    assert last_result["report_sent_to_cu"] is True
    assert last_result["dispatched_ru"] is True

    # 6) 驗證 mock RU 真的收到 5 筆 DlTtiRequest(每 tick 一筆)
    dl_calls = mock_ru.calls_to("/api/v0.1/RU/FAPI/FapiRouter/dl_tti_request")
    assert len(dl_calls) == 5
    for call in dl_calls:
        body = call["payload"]
        assert "sfn" in body and "slot" in body
        # 至少有一筆 pdu 對到 ue-itest
        pdu_ues = {p["ue_id"] for p in body["pdus"]}
        assert "ue-itest" in pdu_ues

    # 7) 驗證 mock CU 在第 5 tick 收到 measurement_report
    mr_calls = mock_cu.calls_to("/api/v0.1/CU/F1AP/F1ApRouter/measurement_report")
    assert len(mr_calls) == 1
    body = mr_calls[0]["payload"]
    assert body["ue_id"] == "ue-itest"
    assert body["rsrp_dbm"] == -82.0
    assert body["sinr_db"] == 18.0
    assert body["mcs_dl"] >= 9
    assert body["rb_width_dl"] > 0


@pytest.mark.django_db
def test_measurement_report_uses_window_average_not_last_sample(mock_cu, mock_ru):
    """每 tick 改變 sinr,跑完 5 tick 後 report 該帶 5 個 sample 的平均,不是最後一筆。"""
    client = Client()
    _post(
        client, "/api/v0.1/DU/F1AP/F1ApRouter/ue_context_setup",
        {"ue_id": "ue-avg", "drbs": [{"drb_id": 1, "qos_5qi": 9, "rlc_mode": "AM"}]},
    )
    _post(
        client, "/api/v0.1/DU/Tick/TickController/register_ue",
        {"ue_id": "ue-avg", "serving_cell": "cell-0", "sinr_db": 0.0, "rsrp_dbm": -100.0},
    )

    runner = get_tick_runner()
    sinrs = [10.0, 12.0, 14.0, 16.0, 18.0]   # mean = 14.0
    rsrps = [-90.0, -88.0, -86.0, -84.0, -82.0]  # mean = -86.0
    for sinr, rsrp in zip(sinrs, rsrps):
        runner.update_ue_sinr("ue-avg", sinr_db=sinr, rsrp_dbm=rsrp)
        # 每 tick 灌一點 SDU 確保被排程
        _post(
            client, "/api/v0.1/DU/RLC/RlcDataController/inject_sdu",
            {"ue_id": "ue-avg", "bearer_type": "DRB", "bearer_id": 1, "sdu_bytes": 1000},
        )
        runner.run_once()

    mr_calls = mock_cu.calls_to("/api/v0.1/CU/F1AP/F1ApRouter/measurement_report")
    assert len(mr_calls) == 1, "5 tick 應只送 1 次 measurement_report"
    body = mr_calls[0]["payload"]
    assert body["ue_id"] == "ue-avg"
    # window 平均(允許 0.1 dB 誤差)
    assert abs(body["sinr_db"] - 14.0) < 0.1, f"expected avg sinr 14.0 got {body['sinr_db']}"
    assert abs(body["rsrp_dbm"] - (-86.0)) < 0.1, f"expected avg rsrp -86 got {body['rsrp_dbm']}"
    # 不能 == 最後一筆,以證明真的是平均
    assert body["sinr_db"] != 18.0
    assert body["rsrp_dbm"] != -82.0
    # throughput 應該是整個 window 的累積 ÷ window_seconds(SIM_TICK_MS=500 → window=2.5s)
    # 5 tick × dl_bytes 在 2.5s 內 → 應 > 0
    assert body["throughput_dl_mbps"] > 0
    # rb_width_dl 是 window 的平均 PRB 用量
    assert body["rb_width_dl"] > 0


@pytest.mark.django_db
def test_release_then_no_schedule(mock_cu, mock_ru):
    """UE release 後即使 sdu 還在 buffer,scheduler 也不該再排到它。"""
    client = Client()
    _post(
        client, "/api/v0.1/DU/F1AP/F1ApRouter/ue_context_setup",
        {"ue_id": "ue-rel", "drbs": [{"drb_id": 1, "qos_5qi": 9, "rlc_mode": "AM"}]},
    )
    _post(
        client, "/api/v0.1/DU/Tick/TickController/register_ue",
        {"ue_id": "ue-rel", "serving_cell": "cell-0", "sinr_db": 20.0},
    )
    _post(
        client, "/api/v0.1/DU/RLC/RlcDataController/inject_sdu",
        {"ue_id": "ue-rel", "bearer_type": "DRB", "bearer_id": 1, "sdu_bytes": 1000},
    )
    runner = get_tick_runner()
    r1 = runner.run_once()
    assert "ue-rel" in r1["scheduled_ues"]

    # release UE — RLC entity & MAC state 都該被清掉
    _post(
        client, "/api/v0.1/DU/F1AP/F1ApRouter/ue_context_release",
        {"ue_id": "ue-rel"},
    )
    # 同時把 tick registry 也拿掉(實際上 ue_context_release 沒做,需手動清)
    runner.unregister_ue("ue-rel")

    r2 = runner.run_once()
    assert r2["scheduled_ues"] == []
    # entity 也該不在 registry
    assert rlc_factory.lookup("ue-rel", "DRB", 1) is None
