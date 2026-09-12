from main.apps.phy_high.services.optional.modulation.modulation_table import mcs_to_modulation


def test_qpsk_low_mcs():
    name, order = mcs_to_modulation(0)
    assert name == "QPSK"
    assert order == 2


def test_64qam_mid_mcs():
    name, order = mcs_to_modulation(15)
    assert name == "64QAM"
    assert order == 6


def test_256qam_high_mcs():
    name, order = mcs_to_modulation(25)
    assert name == "256QAM"
    assert order == 8
