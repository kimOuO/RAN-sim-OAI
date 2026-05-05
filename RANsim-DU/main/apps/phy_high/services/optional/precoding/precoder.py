"""Precoder wrapper — 接 MAC 給的 PMI,呼叫 mimo_processor 算 effective SINR。

實際 channel matrix 由 RU/Physics 提供;這裡只接抽象介面。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from main.apps.phy_high.services.optional.precoding.mimo_processor import (
    MimoResult,
    compute_mimo,
)


@dataclass
class PrecodingDecision:
    pmi: int
    rank: int
    effective_sinr_db: float


def select_precoding(
    *,
    H: np.ndarray | None,
    tx_power_lin: float,
    noise_power_lin: float,
    pmi_hint: int = 0,
) -> PrecodingDecision:
    """簡化:用 SVD-based result 當 effective SINR;PMI 暫不真選 codebook。"""
    if H is None:
        return PrecodingDecision(pmi=pmi_hint, rank=1, effective_sinr_db=0.0)
    res: MimoResult = compute_mimo(H, tx_power_lin=tx_power_lin, noise_power_lin=noise_power_lin)
    if res.rank == 0:
        return PrecodingDecision(pmi=pmi_hint, rank=1, effective_sinr_db=-30.0)
    avg_sinr_db = sum(res.per_stream_sinr_db) / len(res.per_stream_sinr_db)
    return PrecodingDecision(pmi=pmi_hint, rank=res.rank, effective_sinr_db=avg_sinr_db)
