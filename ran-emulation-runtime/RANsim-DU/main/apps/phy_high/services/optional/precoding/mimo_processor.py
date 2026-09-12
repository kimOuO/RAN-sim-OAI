"""MIMO Capacity Processor — SVD-based per-stream SINR for SU-MIMO。

從 RU/Physics 拿到 channel matrix H,計算:
  1. SVD 分解
  2. effective rank (σ ≥ σ_max × threshold)
  3. per-stream SINR
  4. Shannon capacity (上界)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from main.utils.env_loader import get_float


DEFAULT_RANK_THRESHOLD = 0.1


@dataclass
class MimoResult:
    rank: int
    singular_values: list[float]
    per_stream_sinr_db: list[float]
    total_capacity_bps_hz: float
    array_gain_db: float


def compute_mimo(
    H: np.ndarray,
    *,
    tx_power_lin: float,
    noise_power_lin: float,
    rank_threshold: float | None = None,
) -> MimoResult:
    if rank_threshold is None:
        rank_threshold = get_float("MIMO_RANK_THRESHOLD", default=DEFAULT_RANK_THRESHOLD)
    if H.size == 0:
        return MimoResult(0, [], [], 0.0, -300.0)
    try:
        sigmas = np.linalg.svd(H, compute_uv=False)
    except np.linalg.LinAlgError:
        return MimoResult(0, [], [], 0.0, -300.0)
    sigmas = np.asarray(sigmas, dtype=float)
    sigma_max = float(sigmas[0]) if len(sigmas) > 0 else 0.0
    if sigma_max <= 0:
        return MimoResult(0, sigmas.tolist(), [], 0.0, -300.0)
    threshold = sigma_max * rank_threshold
    active_sigmas = sigmas[sigmas >= threshold]
    rank = int(len(active_sigmas))
    if rank == 0:
        return MimoResult(0, sigmas.tolist(), [], 0.0, -300.0)
    p_per_stream = tx_power_lin / rank
    sinr_lin_per_stream = (active_sigmas ** 2) * p_per_stream / max(noise_power_lin, 1e-30)
    sinr_db_per_stream = 10.0 * np.log10(np.maximum(sinr_lin_per_stream, 1e-30))
    capacity = float(np.sum(np.log2(1.0 + sinr_lin_per_stream)))
    total_signal_power = float(np.sum(sigmas ** 2)) * tx_power_lin
    array_gain_db = 10.0 * np.log10(max(total_signal_power, 1e-30) / max(tx_power_lin, 1e-30))
    return MimoResult(
        rank=rank,
        singular_values=sigmas.tolist(),
        per_stream_sinr_db=sinr_db_per_stream.tolist(),
        total_capacity_bps_hz=capacity,
        array_gain_db=array_gain_db,
    )
