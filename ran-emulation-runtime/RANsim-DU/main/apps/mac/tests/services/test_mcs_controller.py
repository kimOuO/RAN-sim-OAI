from main.apps.mac.services.optional.link_adaptation.mcs_controller import (
    MCSController,
    estimate_bler,
)


def test_high_sinr_low_bler():
    bler = estimate_bler(sinr_db=25.0, mcs=9)
    assert bler < 0.01


def test_low_sinr_high_bler():
    bler = estimate_bler(sinr_db=-5.0, mcs=20)
    assert bler > 0.5


def test_mcs_climbs_with_high_sinr():
    ctl = MCSController()
    for tick_ms in range(0, 5000, 50):
        mcs, _ = ctl.update("ue1", sinr_db=25.0, tick_ms_now=tick_ms)
    assert mcs > 9


def test_mcs_drops_with_low_sinr():
    ctl = MCSController()
    for tick_ms in range(0, 5000, 50):
        mcs, _ = ctl.update("ue1", sinr_db=-5.0, tick_ms_now=tick_ms)
    assert mcs < 9
