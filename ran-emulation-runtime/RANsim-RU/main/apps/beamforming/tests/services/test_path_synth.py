"""path_synth:由路徑參數重建元件層 H(階段 C)。

與 Sionna 整個陣列直接算的 H 對拍在 Physics_sim/precompute/experiment_c_path_synth.py(要 GPU);
這裡只驗不需要 Sionna 的性質。
"""
import math

import numpy as np

from main.apps.beamforming.services.optional import path_synth as ps


def _los(k_t, a_vv=1.0):
    A = np.zeros((1, 2, 2), complex)
    A[0, 0, 0] = a_vv
    return A, np.array([k_t], float), np.array([[1.0, 0.0, 0.0]])


def test_element_order_col_slow_row_fast():
    pos = ps.element_positions(2, 3, 0.5, 0.5)
    # 第 0、1 個元件同一欄(y 相同)、不同列(z 不同)
    assert pos[0][1] == pos[1][1] and pos[0][2] > pos[1][2]
    assert pos[2][1] > pos[0][1]


def test_broadside_los_is_all_ones():
    A, kt, kr = _los([1.0, 0.0, 0.0])
    H = ps.synthesize(A, kt, kr, tx=dict(rows=2, cols=4, polarization="V"), rx=dict(), fading=False)
    assert H.shape == (1, 8)
    assert np.allclose(H, 1.0)


def test_steering_phase_matches_horizontal_spacing():
    az = math.radians(30.0)
    A, kt, kr = _los([math.cos(az), math.sin(az), 0.0])
    H = ps.synthesize(A, kt, kr, tx=dict(rows=1, cols=4, polarization="V", horizontal_spacing=0.5), rx=dict(), fading=False)
    step = np.angle(H[0, 1] / H[0, 0])
    assert math.isclose(step, 2 * math.pi * 0.5 * math.sin(az), abs_tol=1e-9)


def test_cross_pol_from_vh():
    # 只有 V→V 路徑:+45° 與 −45° 元件各拿到 cos(±45°) = 1/√2
    A, kt, kr = _los([1.0, 0.0, 0.0])
    H = ps.synthesize(A, kt, kr, tx=dict(polarization="cross"), rx=dict(polarization="V"), fading=False)
    assert H.shape == (1, 2)
    assert np.allclose(np.abs(H), 1 / math.sqrt(2))


def test_rotation_moves_broadside():
    # 陣列轉 90°(α)後,原本正面的方向變成端射:4 個元件的相位差 = π
    A, kt, kr = _los([0.0, 1.0, 0.0])
    H = ps.synthesize(A, kt, kr, tx=dict(rows=1, cols=4, polarization="V"), rx=dict(),
                      tx_orientation=(math.pi / 2, 0.0, 0.0), fading=False)
    assert np.allclose(H, 1.0)


def test_fading_keeps_single_path_power_and_empty_is_zero():
    A, kt, kr = _los([1.0, 0.0, 0.0], a_vv=2.0)
    H = ps.synthesize(A, kt, kr, tx=dict(rows=2, cols=2, polarization="cross"), rx=dict(polarization="cross"),
                      rng=np.random.default_rng(1))
    H0 = ps.synthesize(A, kt, kr, tx=dict(rows=2, cols=2, polarization="cross"), rx=dict(polarization="cross"), fading=False)
    assert math.isclose(np.linalg.norm(H), np.linalg.norm(H0))
    Z = ps.synthesize(np.zeros((3, 2, 2)), np.zeros((3, 3)), np.zeros((3, 3)), tx=dict(rows=2, cols=2, polarization="cross"), rx=dict())
    assert Z.shape == (1, 8) and not np.any(Z)
