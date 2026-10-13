"""TDD 樣式 → 逐 slot DL/UL 權重(38.213 §11.1;special slot 依 OAI band78 6 DL / 4 UL 符號)。"""
import pytest

from main.apps.mac.services.optional.link_adaptation import nr_resources


def test_default_pattern_matches_oai_band78():
    dl, ul = nr_resources._tdd_weights("DDDDDDDSUU")
    assert sum(dl) / len(dl) == pytest.approx(0.742857, abs=1e-6)
    assert sum(ul) / len(ul) == pytest.approx(0.228571, abs=1e-6)


def test_custom_pattern_changes_ratios():
    dl, ul = nr_resources._tdd_weights("DDDSU")
    assert sum(dl) / 5 == pytest.approx((3 + 6 / 14) / 5)
    assert sum(ul) / 5 == pytest.approx((1 + 4 / 14) / 5)


@pytest.mark.parametrize("bad", ["", "DDXU", "ddd s"])
def test_invalid_pattern_rejected(bad):
    with pytest.raises(ValueError):
        nr_resources._tdd_weights(bad.strip().upper() if bad else bad)
