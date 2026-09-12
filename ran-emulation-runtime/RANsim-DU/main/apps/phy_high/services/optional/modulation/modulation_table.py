"""MCS → modulation order 對照表 (3GPP TS 38.214 Table 5.1.3.1-2 256QAM)。"""
from __future__ import annotations


# (mcs_low, mcs_high, modulation_name, modulation_order)
_MCS_RANGES = [
    (0, 4, "QPSK", 2),
    (5, 10, "16QAM", 4),
    (11, 19, "64QAM", 6),
    (20, 27, "256QAM", 8),
]


def mcs_to_modulation(mcs: int) -> tuple[str, int]:
    for lo, hi, name, order in _MCS_RANGES:
        if lo <= mcs <= hi:
            return name, order
    return "QPSK", 2  # default
