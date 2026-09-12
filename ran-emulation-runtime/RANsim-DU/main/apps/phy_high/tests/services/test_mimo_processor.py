import numpy as np

from main.apps.phy_high.services.optional.precoding.mimo_processor import compute_mimo


def test_2x2_identity_rank2():
    H = np.eye(2, dtype=complex)
    res = compute_mimo(H, tx_power_lin=1.0, noise_power_lin=1e-3)
    assert res.rank == 2
    assert all(s > 0 for s in res.per_stream_sinr_db)


def test_zero_matrix_rank0():
    H = np.zeros((2, 2), dtype=complex)
    res = compute_mimo(H, tx_power_lin=1.0, noise_power_lin=1e-3)
    assert res.rank == 0
