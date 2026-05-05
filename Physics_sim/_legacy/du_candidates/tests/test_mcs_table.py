"""測試 SINR → MCS → throughput 查表。不需 GPU。"""
from main.apps.ran_signal.services.optional.ran_calculation.mcs_table import (
    mcs_to_throughput_mbps,
    sinr_to_mcs,
)


def test_very_low_sinr_returns_mcs0():
    mcs, bps = sinr_to_mcs(-20.0)
    assert mcs == 0


def test_high_sinr_returns_top_mcs():
    mcs, bps = sinr_to_mcs(30.0)
    assert mcs == 28


def test_throughput_positive_at_good_sinr():
    mcs, bps = sinr_to_mcs(20.0)
    tput = mcs_to_throughput_mbps(mcs=mcs, bps_re=bps, n_rb=273)
    assert tput > 100
