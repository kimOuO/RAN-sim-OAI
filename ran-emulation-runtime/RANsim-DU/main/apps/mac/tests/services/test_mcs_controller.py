"""外迴路鏈路適應:對齊 OAI get_mcs_from_bler 的行為。"""
from main.apps.mac.services.optional.link_adaptation import bler_curve
from main.apps.mac.services.optional.link_adaptation.mcs_controller import (
    BLER_LOWER,
    BLER_UPDATE_MS,
    BLER_UPPER,
    MIN_MCS,
    MCSController,
)


def _run(ctl: MCSController, sinr: float, seconds: float, step_ms: int = 500) -> int:
    mcs = MIN_MCS
    for t in range(0, int(seconds * 1000) + 1, step_ms):
        mcs, _ = ctl.update("ue1", sinr, t)
    return mcs


def test_new_ue_starts_at_min_mcs_with_mid_bler():
    ctl = MCSController()
    mcs, b = ctl.update("ue1", 20.0, 0)
    assert mcs == MIN_MCS
    assert abs(b - (BLER_LOWER + BLER_UPPER) / 2) < 1e-9


def test_converges_near_operating_point():
    """長時間固定 SINR 後,MCS 停在 OAI 曲線 10% 操作點附近(±2 階,外迴路有滯後帶)。"""
    for sinr in (2.0, 8.0, 14.0, 20.0):
        ctl = MCSController()
        mcs = _run(ctl, sinr, 30.0)
        op = bler_curve.op_point_mcs(sinr)
        assert abs(mcs - op) <= 2, (sinr, mcs, op)
        assert bler_curve.bler(mcs, sinr) <= 0.5


def test_update_cadence_is_sim_time_not_call_count():
    """同一個模擬時間點重複呼叫不會多走一階;步進只看經過的模擬時間。"""
    a, b = MCSController(), MCSController()
    for t in range(0, 3001, 500):          # 每 500 ms 呼叫一次
        a.update("ue1", 25.0, t)
    for t in range(0, 3001, 500):          # 每個時間點連呼三次
        for _ in range(3):
            b.update("ue1", 25.0, t)
    assert a.get_mcs("ue1") == b.get_mcs("ue1")


def test_step_rate_matches_oai_period():
    """高 SINR 下每 100 ms 最多升一階 → 1 秒最多升 10 階。"""
    ctl = MCSController()
    ctl.update("ue1", 30.0, 0)
    mcs, _ = ctl.update("ue1", 30.0, 1000)
    assert mcs <= MIN_MCS + 1000 // BLER_UPDATE_MS


def test_drops_when_sinr_collapses():
    ctl = MCSController()
    high = _run(ctl, 25.0, 10.0)
    for t in range(10_500, 20_001, 500):
        low, _ = ctl.update("ue1", -5.0, t)
    assert low < high
    assert low <= 1


def test_clock_reset_does_not_crash_or_step():
    ctl = MCSController()
    _run(ctl, 20.0, 5.0)
    before = ctl.get_mcs("ue1")
    mcs, _ = ctl.update("ue1", 20.0, 0)      # 場次重啟,時間回到 0
    assert mcs == before


def test_default_thresholds_equal_oai_defaults():
    # TARGET_BLER 預設 0.1(中心)→ 上下門檻 0.15 / 0.05 = OAI dl_bler_target_upper/lower 預設
    assert abs(BLER_UPPER - 0.15) < 1e-12
    assert abs(BLER_LOWER - 0.05) < 1e-12
