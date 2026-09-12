"""驗證 DU 發給 RU 的 DL/UL TTI Request 對到正確的 RU endpoint。"""
from __future__ import annotations

from main.apps.fapi_north.services.business.ru_client_operations import RuClientBusinessService
from main.apps.fapi_north.services.optional.message_codec.fapi_codec import (
    encode_dl_tti,
    encode_ul_tti,
)
from main.apps.fapi_north.services.optional.tti_builder.tti_builder import (
    build_dl_tti,
    build_ul_tti,
)


def test_dl_tti_request_hits_ru_with_correct_url_and_schema(mock_ru):
    msg = build_dl_tti(
        sfn=10, slot=3,
        rb_alloc={"ue1": 50, "ue2": 100},
        mcs_map={"ue1": 9, "ue2": 16},
        pmi_map={"ue1": 0, "ue2": 1},
        rank_map={"ue1": 1, "ue2": 2},
        tbs_map={"ue1": 1500, "ue2": 6000},
        harq_map={"ue1": 0, "ue2": 1},
    )
    ok = RuClientBusinessService.post_dl_tti_request(encode_dl_tti(msg), timeout=2.0)

    assert ok is True
    assert len(mock_ru.calls) == 1
    call = mock_ru.calls[0]
    assert call["path"] == "/api/v0.1/RU/FAPI/FapiRouter/dl_tti_request"
    body = call["payload"]
    assert body["sfn"] == 10
    assert body["slot"] == 3
    assert len(body["pdus"]) == 2
    pdu0 = body["pdus"][0]
    assert pdu0["ue_id"] == "ue1"
    assert pdu0["prb_start"] == 0
    assert pdu0["prb_count"] == 50
    assert pdu0["mcs"] == 9
    pdu1 = body["pdus"][1]
    assert pdu1["prb_start"] == 50
    assert pdu1["prb_count"] == 100
    assert pdu1["layers"] == 2


def test_ul_tti_request_hits_ru(mock_ru):
    msg = build_ul_tti(
        sfn=20, slot=5,
        ul_alloc={"ue1": 30},
        mcs_map={"ue1": 6},
        rank_map={"ue1": 1},
        harq_map={"ue1": 2},
    )
    ok = RuClientBusinessService.post_ul_tti_request(encode_ul_tti(msg), timeout=2.0)

    assert ok is True
    assert mock_ru.calls[0]["path"] == "/api/v0.1/RU/FAPI/FapiRouter/ul_tti_request"
    body = mock_ru.calls[0]["payload"]
    assert body["sfn"] == 20
    assert body["pdus"][0]["harq_pid"] == 2


def test_ru_unreachable_returns_false(monkeypatch):
    monkeypatch.setenv("HTTP_RU_HOST", "127.0.0.1")
    monkeypatch.setenv("HTTP_RU_PORT", "1")
    assert RuClientBusinessService.post_dl_tti_request({"sfn": 0, "slot": 0, "pdus": []}, timeout=0.3) is False
