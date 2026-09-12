"""Precoding：套 PMI 到 channel matrix。

對 OAI: openair1/SCHED_NR/nr_ru_procedures.c::nr_feptx_prec()（IF4p5 模式 RU 端）。
"""
from __future__ import annotations

import numpy as np

from main.apps.beamforming.services.optional import codebook


def _normalization(num_ports: int, num_layers: int) -> float:
    """38.211 §6.3.1.5：每個 W 都要乘 1/sqrt(num_layers * num_ports / num_layers)
    化簡後 = 1/sqrt(num_ports)。"""
    return 1.0 / np.sqrt(num_ports)


def apply_pmi(H: np.ndarray, *, pmi: int, layers: int) -> np.ndarray:
    """H: (num_rx, num_ports) channel matrix。
    回傳 H_eff: (num_rx, num_layers) 等效 channel（已正規化）。
    """
    if H.ndim != 2:
        raise ValueError(f"H must be 2D (num_rx, num_ports), got {H.shape}")
    num_rx, num_ports = H.shape
    W = codebook.lookup(pmi=pmi, layers=layers, ports=num_ports)
    norm = _normalization(num_ports, layers)
    return (H @ W) * norm


def apply_W(H: np.ndarray, W: np.ndarray) -> np.ndarray:
    """直接套外部給的 W（不查 codebook）；W shape = (num_ports, num_layers)。"""
    if H.ndim != 2 or W.ndim != 2:
        raise ValueError("H and W must both be 2D")
    if H.shape[1] != W.shape[0]:
        raise ValueError(f"H ports {H.shape[1]} != W rows {W.shape[0]}")
    norm = _normalization(W.shape[0], W.shape[1])
    return (H @ W) * norm
