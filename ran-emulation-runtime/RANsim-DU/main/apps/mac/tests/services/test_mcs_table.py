"""MCS 表 1 頻譜效率、SINR→MCS 操作點、吞吐量計算。"""
import pytest

from main.apps.mac.services.optional.link_adaptation import bler_curve, nr_resources
from main.apps.mac.services.optional.link_adaptation.mcs_table import (
    goodput_efficiency,
    mcs_to_throughput_mbps,
    sinr_to_mcs,
    spectral_efficiency,
)

# TS 38.214 Table 5.1.3.1-1 的 Spectral efficiency 欄(規範原表數值)
_SPEC_SE = {0: 0.2344, 9: 1.3262, 10: 1.3281, 16: 2.5703, 17: 2.5664, 27: 5.3320, 28: 5.5547}


@pytest.mark.parametrize("mcs,se", sorted(_SPEC_SE.items()))
def test_spectral_efficiency_matches_38214_table1(mcs, se):
    assert spectral_efficiency(mcs) == pytest.approx(se, abs=5e-4)


def test_spectral_efficiency_never_exceeds_64qam_table_max():
    assert max(spectral_efficiency(m) for m in range(29)) == pytest.approx(5.5547, abs=5e-4)


def test_very_low_sinr_returns_mcs0_with_near_zero_goodput():
    mcs, eff = sinr_to_mcs(-20.0)
    assert mcs == 0
    assert eff < 0.01


def test_high_sinr_returns_top_mcs():
    mcs, eff = sinr_to_mcs(30.0)
    assert mcs == 28
    assert eff == pytest.approx(spectral_efficiency(28))


def test_sinr_to_mcs_meets_operating_point():
    for sinr in (0.0, 5.0, 10.0, 15.0, 20.0):
        mcs, _ = sinr_to_mcs(sinr)
        assert bler_curve.bler(mcs, sinr) <= bler_curve.OPERATING_POINT_BLER


def test_throughput_uses_nr_resources():
    tput = mcs_to_throughput_mbps(mcs=20, n_rb=106)
    expect = (nr_resources.bits_per_prb_slot(spectral_efficiency(20)) * 106
              * nr_resources.SLOTS_PER_SEC * nr_resources.tdd_dl_ratio() / 1e6)
    assert tput == pytest.approx(expect)


def test_uplink_uses_uplink_tdd_ratio():
    dl = mcs_to_throughput_mbps(mcs=10, n_rb=10)
    ul = mcs_to_throughput_mbps(mcs=10, n_rb=10, uplink=True)
    assert ul / dl == pytest.approx(nr_resources.tdd_ul_ratio() / nr_resources.tdd_dl_ratio())


def test_goodput_discounts_first_tx_failures():
    mcs, sinr = 20, 14.0
    assert goodput_efficiency(mcs, sinr) == pytest.approx(
        spectral_efficiency(mcs) * (1 - bler_curve.bler(mcs, sinr)))
