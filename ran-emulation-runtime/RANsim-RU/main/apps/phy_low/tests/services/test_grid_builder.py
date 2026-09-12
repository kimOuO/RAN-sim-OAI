from ran_sim_protocol.fapi import DlPduConfig, DlTtiRequest

from main.apps.phy_low.services.optional.grid_builder import build_dl_grid


def test_build_dl_grid_basic():
    req = DlTtiRequest(
        sfn=10, slot=5,
        pdus=[
            DlPduConfig(ue_id="ue-1", prb_start=0, prb_count=20, mcs=10, layers=2, pmi=3),
            DlPduConfig(ue_id="ue-2", prb_start=20, prb_count=30, mcs=15, layers=1, pmi=0),
        ],
    )
    grid = build_dl_grid(req)
    assert grid["sfn"] == 10
    assert grid["slot"] == 5
    assert grid["total_prb_used"] == 50
    assert grid["ue_count"] == 2
    assert grid["prb_alloc"][0]["pmi"] == 3
