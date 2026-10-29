"""DU SINR 用各 cell 真實 TX 功率(2026-10-14 #22):以前假設同功率,與 RU / A3 不一致。"""
import math
from unittest.mock import patch

from main.apps.fapi_north.services.optional import channel_cache_du as ccd


def _sinr(pmap):
    gains = {"a#0": 1e-6, "b#1": 1e-6}               # 同 path gain
    with patch.object(ccd, "_cell_power_map", return_value=pmap), \
         patch.object(ccd, "_cell_freq_map", return_value={}), \
         patch.object(ccd, "_INTER_FREQ", False):
        return ccd.compute_sinr_db(gains, "a#0")


def test_weaker_interferer_power_raises_sinr():
    same = _sinr({"a#0": 10.0, "b#1": 10.0})
    weaker = _sinr({"a#0": 10.0, "b#1": 5.0})        # S3:mid 5 dBm、其他 10 dBm
    assert math.isclose(weaker - same, 5.0, abs_tol=0.3)


def test_unknown_cell_falls_back_to_global_power():
    with patch.object(ccd, "_TX_POWER_DBM", 10.0):
        assert math.isclose(_sinr({}), _sinr({"a#0": 10.0, "b#1": 10.0}), abs_tol=1e-6)
