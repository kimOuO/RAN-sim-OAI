"""SINR → MCS 查表測試。"""
from main.apps.mac.services.optional.link_adaptation.mcs_table import (
    mcs_to_throughput_mbps,
    sinr_to_mcs,
)


def test_very_low_sinr_returns_mcs0():
    mcs, _ = sinr_to_mcs(-20.0)
    assert mcs == 0


def test_high_sinr_returns_top_mcs():
    mcs, _ = sinr_to_mcs(30.0)
    assert mcs == 28


def test_throughput_positive_at_good_sinr():
    mcs, bps = sinr_to_mcs(20.0)
    tput = mcs_to_throughput_mbps(mcs=mcs, bps_re=bps, n_rb=273)
    assert tput > 100
