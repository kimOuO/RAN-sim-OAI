from main.apps.phy_high.services.optional.coding.ldpc_abstract import estimate_bler


def test_low_sinr_high_bler():
    assert estimate_bler(-10.0, 9) > 0.5


def test_high_sinr_low_bler():
    assert estimate_bler(25.0, 9) < 0.05
