"""Codebook 對拍 OAI 表 — 抽幾個關鍵 PMI 驗證。"""
import numpy as np
import pytest

from main.apps.beamforming.services.optional import codebook


def test_supported_configs():
    expected = [(1, 2), (1, 4), (2, 2), (2, 4), (3, 4), (4, 4)]
    assert codebook.supported_configs() == expected


def test_1l_2p_pmi_count():
    assert codebook.num_pmis(layers=1, ports=2) == 6


def test_1l_4p_pmi_count():
    assert codebook.num_pmis(layers=1, ports=4) == 28


def test_1l_2p_pmi_0():
    """OAI nr_W_1l_2p[0] = [[1],[0]]"""
    W = codebook.lookup(pmi=0, layers=1, ports=2)
    np.testing.assert_array_equal(W, np.array([[1.0 + 0j], [0.0 + 0j]]))


def test_1l_2p_pmi_3():
    """OAI nr_W_1l_2p[3] = [[1],[n]] -> [1,-1]"""
    W = codebook.lookup(pmi=3, layers=1, ports=2)
    np.testing.assert_array_equal(W, np.array([[1.0 + 0j], [-1.0 + 0j]]))


def test_1l_2p_pmi_4():
    """OAI nr_W_1l_2p[4] = [[1],[j]] -> [1, 1j]"""
    W = codebook.lookup(pmi=4, layers=1, ports=2)
    np.testing.assert_array_equal(W, np.array([[1.0 + 0j], [0.0 + 1j]]))


def test_2l_4p_pmi_14():
    """OAI nr_W_2l_4p[14] = [[1,1],[1,1],[1,n],[1,n]]"""
    W = codebook.lookup(pmi=14, layers=2, ports=4)
    expected = np.array([
        [1, 1],
        [1, 1],
        [1, -1],
        [1, -1],
    ], dtype=np.complex128)
    np.testing.assert_array_equal(W, expected)


def test_4l_4p_pmi_0_is_identity():
    """OAI nr_W_4l_4p[0] = identity"""
    W = codebook.lookup(pmi=0, layers=4, ports=4)
    np.testing.assert_array_equal(W, np.eye(4, dtype=np.complex128))


def test_invalid_pmi_raises():
    with pytest.raises(codebook.CodebookError):
        codebook.lookup(pmi=99, layers=1, ports=2)


def test_unsupported_config_raises():
    with pytest.raises(codebook.CodebookError):
        codebook.lookup(pmi=0, layers=2, ports=8)
