"""CQI 表:共用套件的表必須等於由目前 BLER 曲線推導的結果。

換了 BLER 曲線卻沒重跑 tools/derive_cqi_thresholds.py 時,這裡會失敗。
"""
import math

import pytest
from ran_sim_protocol import nr_link_tables as t

from main.apps.mac.services.optional.link_adaptation import bler_curve
from main.apps.mac.services.optional.link_adaptation.cqi_table import derive_cqi_thresholds


def test_shared_table_equals_derivation_from_curve():
    assert t.CQI_SINR_THRESHOLDS_DB == derive_cqi_thresholds()


def test_thresholds_monotone_and_complete():
    th = t.CQI_SINR_THRESHOLDS_DB
    assert len(th) == 16 and math.isinf(th[0])
    assert all(a <= b for a, b in zip(th[1:], th[2:]))


def test_cqi_definition_bler_at_most_10_percent():
    """TS 38.214 §5.2.2.1:回報的 CQI 以其調變碼率傳送時 BLER ≤ 0.1。"""
    for sinr in (0.5, 3.0, 7.5, 11.0, 15.0, 19.0, 23.0):
        cqi = t.sinr_to_cqi(sinr)
        mcs = t.mcs_for_cqi(cqi)
        if mcs is not None:
            assert bler_curve.bler(mcs, sinr) <= 0.1 + 1e-9, (sinr, cqi, mcs)


def test_cqi_table1_rows_have_matching_mcs_except_cqi1():
    assert t.mcs_for_cqi(1) is None
    for cqi in range(2, 16):
        assert t.mcs_for_cqi(cqi) is not None


@pytest.mark.parametrize("sinr,cqi", [(-30.0, 0), (30.0, 15)])
def test_extremes(sinr, cqi):
    assert t.sinr_to_cqi(sinr) == cqi
