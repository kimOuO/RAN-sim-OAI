"""SINR (dB) → CQI (0-15) 查表 (對齊 OAI cqi_table2)。"""
from __future__ import annotations


_SINR_TO_CQI_TABLE2 = [
    (-9.0, 0),
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
    (22.7, 15),
]


def sinr_to_cqi(sinr_db: float) -> int:
    if sinr_db < _SINR_TO_CQI_TABLE2[0][0]:
        return 0
    chosen = 0
    for threshold, cqi in _SINR_TO_CQI_TABLE2:
        if sinr_db >= threshold:
            chosen = cqi
    return chosen
