"""5G NR Type I Codebook (38.211 §6.3.1.5) — 直接對拍 OAI 表。

來源：openair1/PHY/MODULATION/nr_modulation.c lines 33-118。
OAI 用 ASCII 編碼複數：'1' → 1, '0' → 0, 'n' → -1, 'j' → 1j, 'o' → -1j。

回傳的 W shape = (num_ports, num_layers)，**未做 1/sqrt(N) 正規化**。
正規化在 precoder.apply_pmi 內統一處理（避免重複乘）。
"""
from __future__ import annotations

import numpy as np


_SYM = {
    "1": 1.0 + 0j,
    "0": 0.0 + 0j,
    "n": -1.0 + 0j,
    "j": 0.0 + 1j,
    "o": 0.0 - 1j,
}


def _decode(rows: list[list[str]]) -> np.ndarray:
    return np.array([[_SYM[c] for c in row] for row in rows], dtype=np.complex128)


# Table 6.3.1.5-1: 1 layer, 2 ports (PMI 0..5)
_W_1L_2P = [
    _decode([["1"], ["0"]]),
    _decode([["0"], ["1"]]),
    _decode([["1"], ["1"]]),
    _decode([["1"], ["n"]]),
    _decode([["1"], ["j"]]),
    _decode([["1"], ["o"]]),
]

# Table 6.3.1.5-3: 1 layer, 4 ports (PMI 0..27)
_W_1L_4P = [
    _decode([["1"], ["0"], ["0"], ["0"]]),
    _decode([["0"], ["1"], ["0"], ["0"]]),
    _decode([["0"], ["0"], ["1"], ["0"]]),
    _decode([["0"], ["0"], ["0"], ["1"]]),
    _decode([["1"], ["0"], ["1"], ["0"]]),
    _decode([["1"], ["0"], ["n"], ["0"]]),
    _decode([["1"], ["0"], ["j"], ["0"]]),
    _decode([["1"], ["0"], ["o"], ["0"]]),
    _decode([["0"], ["1"], ["0"], ["1"]]),
    _decode([["0"], ["1"], ["0"], ["n"]]),
    _decode([["0"], ["1"], ["0"], ["j"]]),
    _decode([["0"], ["1"], ["0"], ["o"]]),
    _decode([["1"], ["1"], ["1"], ["1"]]),
    _decode([["1"], ["1"], ["j"], ["j"]]),
    _decode([["1"], ["1"], ["n"], ["n"]]),
    _decode([["1"], ["1"], ["o"], ["o"]]),
    _decode([["1"], ["j"], ["1"], ["j"]]),
    _decode([["1"], ["j"], ["j"], ["n"]]),
    _decode([["1"], ["j"], ["n"], ["o"]]),
    _decode([["1"], ["j"], ["o"], ["1"]]),
    _decode([["1"], ["n"], ["1"], ["n"]]),
    _decode([["1"], ["n"], ["j"], ["o"]]),
    _decode([["1"], ["n"], ["n"], ["1"]]),
    _decode([["1"], ["n"], ["o"], ["j"]]),
    _decode([["1"], ["o"], ["1"], ["o"]]),
    _decode([["1"], ["o"], ["j"], ["1"]]),
    _decode([["1"], ["o"], ["n"], ["j"]]),
    _decode([["1"], ["o"], ["o"], ["n"]]),
]

# Table 6.3.1.5-4: 2 layers, 2 ports (PMI 0..2)
_W_2L_2P = [
    _decode([["1", "0"], ["0", "1"]]),
    _decode([["1", "1"], ["1", "n"]]),
    _decode([["1", "1"], ["j", "o"]]),
]

# Table 6.3.1.5-5: 2 layers, 4 ports (PMI 0..21)
_W_2L_4P = [
    _decode([["1", "0"], ["0", "1"], ["0", "0"], ["0", "0"]]),
    _decode([["1", "0"], ["0", "0"], ["0", "1"], ["0", "0"]]),
    _decode([["1", "0"], ["0", "0"], ["0", "0"], ["0", "1"]]),
    _decode([["0", "0"], ["1", "0"], ["0", "1"], ["0", "0"]]),
    _decode([["0", "0"], ["1", "0"], ["0", "0"], ["0", "1"]]),
    _decode([["0", "0"], ["0", "0"], ["1", "0"], ["0", "1"]]),
    _decode([["1", "0"], ["0", "1"], ["1", "0"], ["0", "o"]]),
    _decode([["1", "0"], ["0", "1"], ["1", "0"], ["0", "j"]]),
    _decode([["1", "0"], ["0", "1"], ["o", "0"], ["0", "1"]]),
    _decode([["1", "0"], ["0", "1"], ["o", "0"], ["0", "n"]]),
    _decode([["1", "0"], ["0", "1"], ["n", "0"], ["0", "o"]]),
    _decode([["1", "0"], ["0", "1"], ["n", "0"], ["0", "j"]]),
    _decode([["1", "0"], ["0", "1"], ["j", "0"], ["0", "1"]]),
    _decode([["1", "0"], ["0", "1"], ["j", "0"], ["0", "n"]]),
    _decode([["1", "1"], ["1", "1"], ["1", "n"], ["1", "n"]]),
    _decode([["1", "1"], ["1", "1"], ["j", "o"], ["j", "o"]]),
    _decode([["1", "1"], ["j", "j"], ["1", "n"], ["j", "o"]]),
    _decode([["1", "1"], ["j", "j"], ["j", "o"], ["n", "1"]]),
    _decode([["1", "1"], ["n", "n"], ["1", "n"], ["n", "1"]]),
    _decode([["1", "1"], ["n", "n"], ["j", "o"], ["o", "j"]]),
    _decode([["1", "1"], ["o", "o"], ["1", "n"], ["o", "j"]]),
    _decode([["1", "1"], ["o", "o"], ["j", "o"], ["1", "n"]]),
]

# Table 6.3.1.5-6: 3 layers, 4 ports (PMI 0..6)
_W_3L_4P = [
    _decode([["1", "0", "0"], ["0", "1", "0"], ["0", "0", "1"], ["0", "0", "0"]]),
    _decode([["1", "0", "0"], ["0", "1", "0"], ["1", "0", "0"], ["0", "0", "1"]]),
    _decode([["1", "0", "0"], ["0", "1", "0"], ["n", "0", "0"], ["0", "0", "1"]]),
    _decode([["1", "1", "1"], ["1", "n", "1"], ["1", "1", "n"], ["1", "n", "n"]]),
    _decode([["1", "1", "1"], ["1", "n", "1"], ["j", "j", "o"], ["j", "o", "o"]]),
    _decode([["1", "1", "1"], ["n", "1", "n"], ["1", "1", "n"], ["n", "1", "1"]]),
    _decode([["1", "1", "1"], ["n", "1", "n"], ["j", "j", "o"], ["o", "j", "j"]]),
]

# Table 6.3.1.5-7: 4 layers, 4 ports (PMI 0..4)
_W_4L_4P = [
    _decode([["1", "0", "0", "0"], ["0", "1", "0", "0"], ["0", "0", "1", "0"], ["0", "0", "0", "1"]]),
    _decode([["1", "1", "0", "0"], ["0", "0", "1", "1"], ["1", "n", "0", "0"], ["0", "0", "1", "n"]]),
    _decode([["1", "1", "0", "0"], ["0", "0", "1", "1"], ["j", "o", "0", "0"], ["0", "0", "j", "o"]]),
    _decode([["1", "1", "1", "1"], ["1", "n", "1", "n"], ["1", "1", "n", "n"], ["1", "n", "n", "1"]]),
    _decode([["1", "1", "1", "1"], ["1", "n", "1", "n"], ["j", "j", "o", "o"], ["j", "o", "o", "j"]]),
]


_TABLES = {
    (1, 2): _W_1L_2P,
    (1, 4): _W_1L_4P,
    (2, 2): _W_2L_2P,
    (2, 4): _W_2L_4P,
    (3, 4): _W_3L_4P,
    (4, 4): _W_4L_4P,
}


class CodebookError(ValueError):
    pass


def lookup(*, pmi: int, layers: int, ports: int) -> np.ndarray:
    """回傳 W of shape (ports, layers)，未正規化（complex128）。"""
    table = _TABLES.get((layers, ports))
    if table is None:
        raise CodebookError(f"unsupported (layers={layers}, ports={ports}); "
                            f"available {sorted(_TABLES.keys())}")
    if not 0 <= pmi < len(table):
        raise CodebookError(f"pmi {pmi} out of range for (layers={layers}, ports={ports}); "
                            f"max {len(table) - 1}")
    return table[pmi]


def num_pmis(*, layers: int, ports: int) -> int:
    table = _TABLES.get((layers, ports))
    if table is None:
        raise CodebookError(f"unsupported (layers={layers}, ports={ports})")
    return len(table)


def supported_configs() -> list[tuple[int, int]]:
    return sorted(_TABLES.keys())
