"""MIMO Capacity Processor — SVD-based per-stream SINR for SU-MIMO.

從 Sionna 抓到的 channel matrix H 計算：
  1. SVD 分解得到 singular values
  2. Effective rank（σ ≥ threshold 的數量）
  3. Per-stream SINR
  4. Multi-stream throughput（用既有 mcs_table 對每 stream 各自查）

Phase 1 = path_gain → 單 stream RSRP；Phase 2 = H matrix → multi-stream capacity。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from main.utils.env_loader import get_float


# Singular value threshold relative to σ_max — σ < σ_max * RANK_THRESHOLD 視為 noise
DEFAULT_RANK_THRESHOLD = 0.1   # = -20 dB, 約等於 SNR=20 dB 才算可用 stream


@dataclass
class MimoResult:
    """單一 (UE, gNB) 對 MIMO 計算的結果。"""
    rank: int                    # 有效 stream 數量
    singular_values: list[float] # 全部 σ_i（從大到小，含 noise floor 以下的）
    per_stream_sinr_db: list[float]  # 各 stream 的 SINR (dB)，length=rank
    total_capacity_bps_hz: float  # Σ log2(1 + sinr_i)，bits/sec/Hz
    array_gain_db: float         # 跟 SISO 比的等效訊號增益 (dB) = 10·log10(Σσ²)


def compute_mimo(
    H: np.ndarray,
    *,
    tx_power_lin: float,
    noise_power_lin: float,
    rank_threshold: float | None = None,
) -> MimoResult:
    """對單一 (UE, gNB) 對的 channel matrix H 做 SVD-based MIMO 分析。

    Args:
        H: (rx_ant, tx_ant) complex channel matrix
        tx_power_lin: 該 gNB 總發射功率（linear，mW）
        noise_power_lin: 接收端 thermal noise + NF (linear，mW)
        rank_threshold: σ_i < σ_max * threshold 視為 noise，預設 0.1 (-20 dB)

    Returns: MimoResult
    """
    if rank_threshold is None:
        rank_threshold = get_float("MIMO_RANK_THRESHOLD", default=DEFAULT_RANK_THRESHOLD)

    if H.size == 0:
        return MimoResult(
            rank=0, singular_values=[], per_stream_sinr_db=[],
            total_capacity_bps_hz=0.0, array_gain_db=-300.0,
        )

    # SVD：σ_i 由大到小排序
    try:
        sigmas = np.linalg.svd(H, compute_uv=False)
    except np.linalg.LinAlgError:
        return MimoResult(
            rank=0, singular_values=[], per_stream_sinr_db=[],
            total_capacity_bps_hz=0.0, array_gain_db=-300.0,
        )

    sigmas = np.asarray(sigmas, dtype=float)
    sigma_max = float(sigmas[0]) if len(sigmas) > 0 else 0.0

    # 有效 rank：σ ≥ σ_max × threshold
    if sigma_max <= 0:
        return MimoResult(
            rank=0, singular_values=sigmas.tolist(), per_stream_sinr_db=[],
            total_capacity_bps_hz=0.0, array_gain_db=-300.0,
        )
    threshold = sigma_max * rank_threshold
    active_sigmas = sigmas[sigmas >= threshold]
    rank = int(len(active_sigmas))
    if rank == 0:
        return MimoResult(
            rank=0, singular_values=sigmas.tolist(), per_stream_sinr_db=[],
            total_capacity_bps_hz=0.0, array_gain_db=-300.0,
        )

    # Per-stream SINR：每 stream 拿到 P_total / num_streams 的功率
    p_per_stream = tx_power_lin / rank
    sinr_lin_per_stream = (active_sigmas ** 2) * p_per_stream / max(noise_power_lin, 1e-30)
    sinr_db_per_stream = 10.0 * np.log10(np.maximum(sinr_lin_per_stream, 1e-30))

    # Shannon capacity (bps/Hz) — 上限值
    capacity = float(np.sum(np.log2(1.0 + sinr_lin_per_stream)))

    # Array gain：跟 SISO 比，相當於把所有 |σ|² 加總當訊號
    total_signal_power = float(np.sum(sigmas ** 2)) * tx_power_lin
    array_gain_db = 10.0 * np.log10(max(total_signal_power, 1e-30) / max(tx_power_lin, 1e-30))

    return MimoResult(
        rank=rank,
        singular_values=sigmas.tolist(),
        per_stream_sinr_db=sinr_db_per_stream.tolist(),
        total_capacity_bps_hz=capacity,
        array_gain_db=array_gain_db,
    )
