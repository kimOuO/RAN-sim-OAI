import pytest

from main.apps.phy_low.services.optional.ofdm_descriptor import (
    OfdmDescriptorError,
    describe_ofdm,
)


def test_numerology_1_30khz():
    d = describe_ofdm(1, bandwidth_mhz=100)
    assert d["scs_khz"] == 30
    assert d["slots_per_subframe"] == 2
    assert d["fft_size"] == 4096


def test_numerology_3_120khz():
    d = describe_ofdm(3, bandwidth_mhz=100)
    assert d["scs_khz"] == 120
    assert d["slots_per_subframe"] == 8


def test_invalid_numerology():
    with pytest.raises(OfdmDescriptorError):
        describe_ofdm(99)
