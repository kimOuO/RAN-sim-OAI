"""SINR → MCS → throughput 查表（簡化 3GPP TS 38.214 Table 5.1.3.1-2）。

並非精確 CQI/MCS mapping；夠用作 E2 上報的 throughput 估算。
"""


# (SINR dB 下限, MCS, bits per RE)
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
    slots_per_sec: int = 2000,  # 30 kHz SCS，20 slot/subframe × 1000 subframe/s ÷ 10 = 2000
    overhead: float = 0.85,     # 扣 PDCCH/DMRS 等 overhead
) -> int:
    """n_rb * 12 RE/RB * symbols/slot * slots/s * bits/RE * overhead / 1e6 → Mbps。"""
    re_per_slot = n_rb * 12 * n_symbols_per_slot
    bits_per_slot = re_per_slot * bps_re
    bits_per_sec = bits_per_slot * slots_per_sec * overhead
    return max(0, int(bits_per_sec / 1e6))
