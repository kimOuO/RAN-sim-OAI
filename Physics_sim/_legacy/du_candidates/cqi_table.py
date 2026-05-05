"""SINR (dB) → CQI (0-15) 查表。

真 OAI 的 CQI 是 UE 從 CSI-RS 量完回報的；我們 compute-only 場景無 UE CSI，
從 SINR 反推 CQI。依 3GPP TS 38.214 §5.2.2.1 的 cqi_table2（256QAM 能力）
對應的 SINR 門檻（近似，各家實作略有差異）。

Source: cqi_table2 in OAI gNB_scheduler_primitives.c lines 90-105
"""


# SINR(dB) 下限 → CQI；按升序排列；
# 數值來自常用經驗 mapping（對 SISO / AWGN）。
_SINR_TO_CQI_TABLE2 = [
    (-9.0, 0),    # CQI 0 = out of range
    (-6.7, 1),
    (-4.7, 2),
    (-2.3, 3),
    (0.2, 4),
    (2.4, 5),
    (4.3, 6),
    (5.9, 7),
    (8.1, 8),
    (10.3, 9),
    (11.7, 10),
    (14.1, 11),
    (16.3, 12),
    (18.7, 13),
    (21.0, 14),
    (22.7, 15),   # CQI 15 = highest (256QAM R=948)
]


def sinr_to_cqi(sinr_db: float) -> int:
    """SINR → CQI(0-15)。超過上界回 15；低於下界回 0。"""
    if sinr_db < _SINR_TO_CQI_TABLE2[0][0]:
        return 0
    chosen = 0
    for threshold, cqi in _SINR_TO_CQI_TABLE2:
        if sinr_db >= threshold:
            chosen = cqi
    return chosen
