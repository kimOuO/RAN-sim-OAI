"""SINR → MCS → throughput 查表(簡化 3GPP TS 38.214 Table 5.1.3.1-2)。

不是精確 CQI/MCS mapping;夠用作 throughput 估算與 PF metric。
"""
from __future__ import annotations


# OAI band78 DDDDDDDSUU pattern (nrofDownlinkSlots=7, special slot DL 6/14 symbols,
# UL=2, period=5ms = 10 slots @ 30kHz SCS) → 有效 DL slot 比例 ≈ 7.43/10 = 0.743。
# 取保守 0.72(含 PDCCH/SSB 額外占用)。對齊 OAI gnb-du.sa.band78.106prb conf。
TDD_DL_SLOT_RATIO: float = 0.72


_SINR_TO_MCS = [
    (-6, 0, 0.23),
    (-4, 2, 0.38),
    (-2, 4, 0.60),
    (0, 6, 0.88),
    (2, 8, 1.18),
    (4, 10, 1.48),
    (6, 12, 1.91),
    (8, 14, 2.41),
    (10, 16, 2.73),
    (12, 18, 3.32),
    (14, 20, 3.90),
    (16, 22, 4.52),
    (18, 24, 5.12),
    (20, 26, 5.55),
    (22, 27, 5.85),
    (25, 28, 7.41),
]


def sinr_to_mcs(sinr_db: float) -> tuple[int, float]:
    if sinr_db < _SINR_TO_MCS[0][0]:
        return (0, 0.0)
    chosen = _SINR_TO_MCS[0]
    for threshold, mcs, bps_re in _SINR_TO_MCS:
        if sinr_db >= threshold:
            chosen = (threshold, mcs, bps_re)
    return (chosen[1], chosen[2])


def mcs_to_throughput_mbps(
    *,
    mcs: int,
    bps_re: float,
    n_rb: int,
    n_symbols_per_slot: int = 12,
    slots_per_sec: int = 2000,
    overhead: float = 0.80,
    tdd_dl_ratio: float = TDD_DL_SLOT_RATIO,
) -> float:
    re_per_slot = n_rb * 12 * n_symbols_per_slot
    bits_per_slot = re_per_slot * bps_re
    bits_per_sec = bits_per_slot * slots_per_sec * overhead * tdd_dl_ratio
    return max(0.0, bits_per_sec / 1e6)
