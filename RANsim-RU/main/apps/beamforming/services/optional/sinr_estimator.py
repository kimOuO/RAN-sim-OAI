"""SINR / Rank / CQI 估算 — UE-side 量測模型。

簡化模型（不真做 LDPC）：
  SINR_per_layer ≈ |H_eff[:, k]|^2 / noise_linear     (k = layer index)
  總 SINR    = 平均（dB 之 mean，避免極大值主導）
  Rank       = H_eff 條件數合理時取 H 的 effective rank
  CQI table  = 38.214 Table 5.2.2.1-2（簡化 16-grade map）
"""
from __future__ import annotations

import numpy as np


def _to_db(linear: float) -> float:
    return 10.0 * np.log10(max(linear, 1e-30))


def _from_dbm(dbm: float) -> float:
    return 10.0 ** ((dbm - 30.0) / 10.0)  # mW → W


def estimate_sinr(H_eff: np.ndarray, noise_dbm: float) -> float:
    """H_eff: (num_rx, num_layers)。回傳 SINR (dB)。"""
    if H_eff.size == 0:
        return -float("inf")
    noise_w = _from_dbm(noise_dbm)
    # per-layer signal power = ||H_eff[:, k]||^2
    sig_per_layer = np.sum(np.abs(H_eff) ** 2, axis=0)  # shape (num_layers,)
    # 平均 SINR：先在 linear 平均，再轉 dB
    mean_sig = float(np.mean(sig_per_layer))
    return _to_db(mean_sig / noise_w)


def estimate_rank(H_eff: np.ndarray, *, sv_ratio_threshold: float = 0.1) -> int:
    """以 H_eff 的 singular value 比例估 effective rank。"""
    if H_eff.size == 0:
        return 0
    s = np.linalg.svd(H_eff, compute_uv=False)
    if s.size == 0:
        return 0
    smax = float(s.max())
    if smax == 0:
        return 0
    significant = int(np.sum(s / smax > sv_ratio_threshold))
    return max(1, significant)


# 38.214 Table 5.2.2.1-2 的簡化版 (CQI 0..15)：以 SINR(dB) 切點查表。
# 低於 -6 dB → CQI 0；高於 22.7 dB → CQI 15。
_CQI_THRESHOLDS_DB = [
    -float("inf"), -6.0, -4.0, -2.0, 0.0, 2.0, 4.0, 6.0,
    8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0,
]


def sinr_to_cqi(sinr_db: float) -> int:
    """SINR (dB) → CQI 0..15。"""
    cqi = 0
    for i, th in enumerate(_CQI_THRESHOLDS_DB):
        if sinr_db >= th:
            cqi = i
        else:
            break
    return min(cqi, 15)
