"""SINR estimator 測試。"""
import math

import numpy as np

from main.apps.beamforming.services.optional import sinr_estimator


def test_sinr_to_cqi_low():
    assert sinr_estimator.sinr_to_cqi(-10) == 0


def test_sinr_to_cqi_mid():
    assert sinr_estimator.sinr_to_cqi(0) == 4
    assert sinr_estimator.sinr_to_cqi(10) == 9


def test_sinr_to_cqi_max():
    assert sinr_estimator.sinr_to_cqi(30) == 15


def test_sinr_to_cqi_clamp_top():
    assert sinr_estimator.sinr_to_cqi(100) == 15


def test_estimate_rank_full_rank_identity():
    H = np.eye(4, dtype=np.complex128)
    assert sinr_estimator.estimate_rank(H) == 4


def test_estimate_rank_low_rank():
    H = np.zeros((4, 4), dtype=np.complex128)
    H[0, 0] = 1.0
    assert sinr_estimator.estimate_rank(H) == 1


def test_estimate_sinr_increases_with_signal():
    H1 = np.eye(2, dtype=np.complex128) * 0.01
    H2 = np.eye(2, dtype=np.complex128) * 1.0
    s1 = sinr_estimator.estimate_sinr(H1, noise_dbm=-95)
    s2 = sinr_estimator.estimate_sinr(H2, noise_dbm=-95)
    assert s2 > s1
    assert math.isfinite(s1) and math.isfinite(s2)
