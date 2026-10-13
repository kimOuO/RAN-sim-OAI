"""OAI AWGN BLER 曲線:載入、內插、嚴格檢查、HARQ 輪次。"""
import math

import pytest

from main.apps.mac.services.optional.link_adaptation import bler_curve


@pytest.fixture(autouse=True)
def _fresh_curve(monkeypatch):
    monkeypatch.delenv("SIM_BLER_CURVE_PATH", raising=False)
    bler_curve.reset_cache()
    yield
    bler_curve.reset_cache()


def test_covers_all_mcs_of_table1():
    for m in range(29):
        assert 0.0 <= bler_curve.bler(m, 10.0) <= 1.0


def test_matches_oai_raw_data_points():
    # OAI mcs9_awgn_5G.csv:SNR 4.5 → err0/trials0 = 853/1500;SNR 5 → 96/1500
    assert bler_curve.bler(9, 4.5) == pytest.approx(853 / 1500, abs=1e-4)
    assert bler_curve.bler(9, 5.0) == pytest.approx(96 / 1500, abs=1e-4)


def test_low_and_high_sinr_extremes():
    assert bler_curve.bler(9, -10.0) > 0.99
    assert bler_curve.bler(9, 25.0) < 0.01


def test_sinr_at_bler_is_where_curve_crosses_target():
    for m in (0, 9, 20, 27):
        th = bler_curve.sinr_at_bler(m, 0.1)
        assert bler_curve.bler(m, th) == pytest.approx(0.1, abs=0.02)
        assert bler_curve.bler(m, th + 0.5) <= 0.1


def test_op_point_mcs_monotone_in_sinr():
    prev = -1
    for s in range(-5, 30):
        m = bler_curve.op_point_mcs(float(s))
        assert m >= prev
        prev = m


def test_missing_file_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("SIM_BLER_CURVE_PATH", str(tmp_path / "nope.csv"))
    bler_curve.reset_cache()
    with pytest.raises(RuntimeError):
        bler_curve.bler(9, 5.0)


def test_incomplete_file_raises(monkeypatch, tmp_path):
    p = tmp_path / "partial.csv"
    p.write_text("mcs,sinr_db,bler\n0,-10,1.0\n0,-7,0.1\n9,5,0.1\n")
    monkeypatch.setenv("SIM_BLER_CURVE_PATH", str(p))
    bler_curve.reset_cache()
    with pytest.raises(RuntimeError, match="缺少 MCS"):
        bler_curve.bler(9, 5.0)


def test_harq_round_probs_sum_and_combining_gain():
    reach, fail = bler_curve.harq_round_probs(20, 14.0)
    assert reach[0] == 1.0
    assert all(a >= b for a, b in zip(reach, reach[1:]))
    # 第 2 次傳送合併 2 份副本 → 失敗機率比首傳低
    b0 = bler_curve.bler(20, 14.0)
    assert reach[1] == pytest.approx(b0)
    assert reach[2] / reach[1] == pytest.approx(bler_curve.bler(20, 14.0 + 10 * math.log10(2)))
    assert 0.0 <= fail <= reach[-1]
