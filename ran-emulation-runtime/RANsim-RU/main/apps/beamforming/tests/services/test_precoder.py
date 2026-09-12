"""apply_pmi 驗證 — H_eff shape 與正規化。"""
import numpy as np

from main.apps.beamforming.services.optional import precoder


def test_apply_pmi_shape_2x2():
    H = np.eye(2, dtype=np.complex128)
    H_eff = precoder.apply_pmi(H, pmi=0, layers=1)
    assert H_eff.shape == (2, 1)


def test_apply_pmi_shape_4x4_to_4layers():
    H = np.eye(4, dtype=np.complex128)
    H_eff = precoder.apply_pmi(H, pmi=0, layers=4)
    assert H_eff.shape == (4, 4)


def test_apply_pmi_normalized_unit_power():
    """PMI 0 (1L,2P) = e1，正規化後 ||W|| = 1/sqrt(2)；對 H=I 套出來 |H_eff[0,0]| = 1/sqrt(2)。"""
    H = np.eye(2, dtype=np.complex128)
    H_eff = precoder.apply_pmi(H, pmi=0, layers=1)
    expected = np.array([[1.0], [0.0]]) / np.sqrt(2)
    np.testing.assert_allclose(H_eff, expected)


def test_apply_pmi_2l_2p_orthogonal():
    """PMI 0 (2L,2P) = I → H @ I/sqrt(2) 結果應正交。"""
    H = np.eye(2, dtype=np.complex128)
    H_eff = precoder.apply_pmi(H, pmi=0, layers=2)
    # H_eff = I/sqrt(2)；兩行內積為 0
    inner = H_eff[:, 0].conj() @ H_eff[:, 1]
    assert abs(inner) < 1e-12
