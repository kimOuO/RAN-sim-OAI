from main.apps.fapi_north.services.optional.tti_builder.tti_builder import (
    build_dl_tti,
    build_ul_tti,
)


def test_build_dl_tti_assigns_consecutive_prb():
    rb_alloc = {"ue1": 10, "ue2": 20}
    msg = build_dl_tti(
        sfn=0, slot=0, rb_alloc=rb_alloc, mcs_map={"ue1": 9, "ue2": 12},
        pmi_map={"ue1": 0, "ue2": 1},
        rank_map={"ue1": 1, "ue2": 2},
        tbs_map={"ue1": 1500, "ue2": 3000},
        harq_map={"ue1": 0, "ue2": 1},
    )
    assert len(msg.pdus) == 2
    assert msg.pdus[0].prb_start == 0
    assert msg.pdus[0].prb_count == 10
    assert msg.pdus[1].prb_start == 10
    assert msg.pdus[1].prb_count == 20


def test_skip_zero_prb():
    msg = build_dl_tti(sfn=1, slot=2, rb_alloc={"ue1": 0, "ue2": 5}, mcs_map={"ue2": 9})
    assert len(msg.pdus) == 1
    assert msg.pdus[0].ue_id == "ue2"


def test_build_ul_tti_basic():
    msg = build_ul_tti(sfn=10, slot=5, ul_alloc={"ue1": 8}, mcs_map={"ue1": 6})
    assert msg.sfn == 10 and msg.slot == 5
    assert msg.pdus[0].mcs == 6
