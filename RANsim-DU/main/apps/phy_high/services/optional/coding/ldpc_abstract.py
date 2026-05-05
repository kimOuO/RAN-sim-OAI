"""LDPC 抽象 — 不做位元級,用 BLER curve 模擬 decode 成功 / 失敗。

BLER curve 由 mcs_controller 的 SINR_REQUIRED_DB 推導,讀 csv 是 optional;
若檔案不存在,fallback 到內建公式。
"""
from __future__ import annotations

import csv
import math
import random
from pathlib import Path

from main.utils.env_loader import get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)


_MCS_SINR_REQUIRED_DB = [
    -7.0, -5.0, -3.0, -1.0, 1.0, 3.0, 5.0, 7.0,
    9.0, 11.0, 13.0, 14.5, 16.0, 17.5, 19.0, 20.0,
    20.8, 21.5, 22.2, 22.9, 23.6, 24.3, 25.0, 25.7,
    26.5, 27.2, 28.0, 28.8,
]
SIGMA_DB = 1.5
_curve_cache: dict[int, list[tuple[float, float]]] | None = None


def _load_curve() -> dict[int, list[tuple[float, float]]] | None:
    """讀 SIM_BLER_CURVE_PATH csv,格式: mcs,sinr_db,bler"""
    global _curve_cache
    if _curve_cache is not None:
        return _curve_cache
    raw = get_str("SIM_BLER_CURVE_PATH", "")
    # 沒設 / 空字串 / 不存在 / 是目錄 → 跳過 csv，走 formula fallback
    if not raw:
        _curve_cache = {}
        return _curve_cache
    path = Path(raw)
    if not path.is_file():
        _curve_cache = {}
        return _curve_cache
    table: dict[int, list[tuple[float, float]]] = {}
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                mcs = int(row["mcs"])
                sinr = float(row["sinr_db"])
                bler = float(row["bler"])
            except (KeyError, ValueError):
                continue
            table.setdefault(mcs, []).append((sinr, bler))
    for mcs in table:
        table[mcs].sort(key=lambda x: x[0])
    _curve_cache = table
    logger.info("Loaded BLER curve: %d MCS entries from %s", len(table), path)
    return _curve_cache


def estimate_bler(sinr_db: float, mcs: int) -> float:
    """先查 csv,若沒有就用公式 fallback。"""
    table = _load_curve() or {}
    if mcs in table and table[mcs]:
        # 線性插值
        pts = table[mcs]
        if sinr_db <= pts[0][0]:
            return pts[0][1]
        if sinr_db >= pts[-1][0]:
            return pts[-1][1]
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            if x0 <= sinr_db <= x1:
                t = (sinr_db - x0) / (x1 - x0)
                return y0 + t * (y1 - y0)
    if mcs < 0 or mcs >= len(_MCS_SINR_REQUIRED_DB):
        return 1.0
    margin = sinr_db - _MCS_SINR_REQUIRED_DB[mcs]
    return max(0.0, min(1.0, 0.5 * math.erfc(margin / (SIGMA_DB * math.sqrt(2)))))


def simulate_decode(sinr_db: float, mcs: int, rng: random.Random | None = None) -> bool:
    """回傳 decode 成功與否(隨機取樣 BLER)。"""
    rng = rng or random
    bler = estimate_bler(sinr_db, mcs)
    return rng.random() >= bler
