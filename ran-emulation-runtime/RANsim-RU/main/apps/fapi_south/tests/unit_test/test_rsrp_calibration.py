"""AC3 — RSRP calibration regression test.

Lock _path_gain_to_rsrp_dbm() 行為, 防止 AC1 calibration 常數 (TX/antenna/scene_loss)
被誤改後 RSRP 又 saturate 回 -31 dBm encoding ceiling.

3GPP TS 38.215 §5.1.1 RSRP-Range encoding: integer 0..127, mapping to [-156, -31] dBm.
若 sim 出 RSRP > -31 dBm, RIC 端 mobiflow KPM Indication encoder 會 cap 在 127,
所有近 UE 看起來都一樣強 → handover scenario 無法 demo.
"""
import importlib
import os
from unittest import TestCase, mock


class RsrpCalibrationTests(TestCase):

    def test_close_ue_path_gain_yields_realistic_rsrp(self):
        """近 UE: path_gain_linear=0.001 (即 -30 dB) → RSRP ≈ -23 dBm。"""
        from main.apps.fapi_south.services.optional.dl_tti_pipeline import (
            _path_gain_to_rsrp_dbm,
        )
        rsrp = _path_gain_to_rsrp_dbm(0.001)
        # default 50 dB cal, TX=43, gain=14: RSRP = 43+14+(-30)-50 = -23 dBm
        self.assertGreater(rsrp, -25)
        self.assertLess(rsrp, -21)

    def test_mid_distance_ue_rsrp_in_realistic_range(self):
        """中距 UE: path_gain_linear=1e-7 (即 -70 dB) → RSRP ≈ -63 dBm。"""
        from main.apps.fapi_south.services.optional.dl_tti_pipeline import (
            _path_gain_to_rsrp_dbm,
        )
        rsrp = _path_gain_to_rsrp_dbm(1e-7)
        # 43+14+(-70)-50 = -63
        self.assertGreater(rsrp, -65)
        self.assertLess(rsrp, -61)

    def test_far_ue_below_saturate_range(self):
        """遠 UE: path_gain_linear=1e-10 (即 -100 dB) → RSRP ≈ -93 dBm (cell edge)。"""
        from main.apps.fapi_south.services.optional.dl_tti_pipeline import (
            _path_gain_to_rsrp_dbm,
        )
        rsrp = _path_gain_to_rsrp_dbm(1e-10)
        # 43+14+(-100)-50 = -93
        self.assertGreater(rsrp, -95)
        self.assertLess(rsrp, -91)

    def test_no_signal_returns_sentinel(self):
        """path_gain_linear=0 / None → -200 dBm sentinel。"""
        from main.apps.fapi_south.services.optional.dl_tti_pipeline import (
            _path_gain_to_rsrp_dbm,
        )
        self.assertEqual(_path_gain_to_rsrp_dbm(0.0), -200.0)
        self.assertEqual(_path_gain_to_rsrp_dbm(None), -200.0)
        self.assertEqual(_path_gain_to_rsrp_dbm(-1e-15), -200.0)

    def test_calibration_env_var_takes_effect(self):
        """RU_SCENE_CALIBRATION_LOSS_DB env override 會被 module load 時讀進來."""
        with mock.patch.dict(os.environ, {"RU_SCENE_CALIBRATION_LOSS_DB": "30.0"}):
            from main.apps.fapi_south.services.optional import dl_tti_pipeline
            importlib.reload(dl_tti_pipeline)
            try:
                rsrp = dl_tti_pipeline._path_gain_to_rsrp_dbm(0.001)
                # 43+14+(-30)-30 = -3 dBm; 比 default -23 高 20 dB (cal 從 50→30)
                self.assertGreater(rsrp, -5)
                self.assertLess(rsrp, -1)
            finally:
                os.environ.pop("RU_SCENE_CALIBRATION_LOSS_DB", None)
                importlib.reload(dl_tti_pipeline)

    def test_no_saturate_for_typical_close_ue(self):
        """AC1 主要目標 — 近 UE (path_gain 範圍 -10 到 -50 dB) RSRP 不超過 0 dBm。

        Pre-AC1 sim 沒 calibration loss, 最近 UE RSRP 算到 +20 dBm,
        RIC 看到 saturate (encoder cap 在 -31 dBm = value 127).
        AC1 加 50 dB scene loss 後, 近 UE RSRP 落在 -3 ~ -43 dBm 範圍, 不再 saturate.
        """
        from main.apps.fapi_south.services.optional.dl_tti_pipeline import (
            _path_gain_to_rsrp_dbm,
        )
        for pg_db in [-10, -20, -30, -40, -50]:
            pg_linear = 10 ** (pg_db / 10.0)
            rsrp = _path_gain_to_rsrp_dbm(pg_linear)
            # default cal=50, TX=43, gain=14: RSRP = 7 + pg_db
            # 不 saturate: 全部 < 0 dBm
            self.assertLess(rsrp, 0, f"path_gain={pg_db}dB → RSRP={rsrp} should be < 0")
