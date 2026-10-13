"""SINR / Rank / CQI 估算 — UE-side 量測模型。

簡化模型（不真做 LDPC）：
  SINR_per_layer ≈ |H_eff[:, k]|^2 / noise_linear     (k = layer index)
  總 SINR    = 平均（dB 之 mean，避免極大值主導）
  Rank       = H_eff 條件數合理時取 H 的 effective rank
  CQI table  = 38.214 Table 5.2.2.1-2（簡化 16-grade map）
"""
from __future__ import annotations

import numpy as np
from ran_sim_protocol.nr_link_tables import sinr_to_cqi as _shared_sinr_to_cqi


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


def sinr_to_cqi(sinr_db: float) -> int:
    """SINR (dB) → CQI 0..15,依 TS 38.214 §5.2.2.1(BLER ≤ 0.1 的最高 CQI)。

    切點由 OAI AWGN BLER 曲線推導,與 DU 共用同一張表(ran_sim_protocol.nr_link_tables)。
    2026-09-26 前這裡是一張每 2 dB 一格的手寫表,與 DU 的表不同、兩者皆無出處。
    """
    return _shared_sinr_to_cqi(sinr_db)
