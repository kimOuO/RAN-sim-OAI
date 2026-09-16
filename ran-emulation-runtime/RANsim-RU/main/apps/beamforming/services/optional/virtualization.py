"""元件 → TXRU 虛擬化(TR 38.901 §7.3.1)。

三層天線模型的第一層映射(見 new_plan/ru_antenna_mimo_plan.md):

    元件層 (Mg,Ng,M,N,P)  ──本模組 W_virt──▶  TRX 層  ──codebook──▶  埠層

每個 TXRU 垂直帶 `v_group` 片同極化元件,元件間用固定相位差合成電子下傾。
權重直接用 TR 38.901 式 (7.3-1):

    w_m = (1/√M) · exp( −j · 2π/λ · (m−1) · d_V · cos θ_etilt ),  m = 1…M

其中 θ_etilt 是電子傾斜角(0°–180°,90° = 垂直於陣列面,即不傾斜),d_V 是垂直元件間距(λ)。
本專案的 `electrical_tilt_deg` 定義為「正 = 往下」,故 θ_etilt = 90° + electrical_tilt_deg。

元件索引順序對齊 **Sionna RT**(sionna/rt/path_solvers/paths.py:818,維度為
[..., num_tx_patterns, tx_array_size, ...],flatten 後極化是慢索引、位置是快索引;
PlanarArray 的位置又是 col 慢、row 快):

    elem_index = pol * (Mg·Ng·M·N) + panel * (M·N) + col * M + row
"""
from __future__ import annotations

import numpy as np


def n_pol(polarization: str) -> int:
    """極化數 P:cross / VH = 2,其餘 = 1。"""
    return 2 if str(polarization).lower() in ("cross", "vh", "dual") else 1


def element_count(*, rows: int, cols: int, polarization: str = "V", panels_mg: int = 1, panels_ng: int = 1) -> int:
    return int(panels_mg) * int(panels_ng) * int(rows) * int(cols) * n_pol(polarization)


def trx_count(*, rows: int, cols: int, polarization: str = "V", panels_mg: int = 1, panels_ng: int = 1,
              v_group: int = 1) -> int:
    """TXRU 數 = 面板數 × (M / v_group) × N × P。v_group 需整除 rows。"""
    v_group = max(1, int(v_group))
    if int(rows) % v_group:
        raise ValueError(f"trx_v_group={v_group} 無法整除 rows={rows}")
    return int(panels_mg) * int(panels_ng) * (int(rows) // v_group) * int(cols) * n_pol(polarization)


def tilt_weights(v_group: int, *, v_spacing: float, electrical_tilt_deg: float) -> np.ndarray:
    """TR 38.901 式 (7.3-1):一個 TXRU 底下 v_group 片元件的複數權重(已正規化)。"""
    m = np.arange(int(v_group))
    theta_etilt = np.deg2rad(90.0 + float(electrical_tilt_deg))
    w = np.exp(-2j * np.pi * m * float(v_spacing) * np.cos(theta_etilt))
    return w / np.sqrt(max(1, int(v_group)))


def build(*, rows: int, cols: int, polarization: str = "V", panels_mg: int = 1, panels_ng: int = 1,
          v_group: int = 1, v_spacing: float = 0.5, electrical_tilt_deg: float = 0.0) -> np.ndarray:
    """回傳 W_virt,shape = (n_elem, n_trx)。

    H_trx = H_elem @ W_virt,H_elem 的 tx 維度必須是上面說的 Sionna 元件順序。
    v_group = 1 時退化成單位矩陣(一片元件 = 一個 TXRU),舊行為不變。
    """
    M, N = int(rows), int(cols)
    P = n_pol(polarization)
    Mg, Ng = int(panels_mg), int(panels_ng)
    V = max(1, int(v_group))
    if M % V:
        raise ValueError(f"trx_v_group={V} 無法整除 rows={M}")
    n_panel = Mg * Ng
    n_elem = n_panel * M * N * P
    n_vgrp = M // V
    n_trx = n_panel * n_vgrp * N * P

    W = np.zeros((n_elem, n_trx), dtype=np.complex128)
    w_col = tilt_weights(V, v_spacing=v_spacing, electrical_tilt_deg=electrical_tilt_deg)
    t = 0
    for pol in range(P):
        for panel in range(n_panel):
            for col in range(N):
                for g in range(n_vgrp):
                    base = pol * (n_panel * M * N) + panel * (M * N) + col * M
                    for k in range(V):
                        W[base + g * V + k, t] = w_col[k]
                    t += 1
    assert t == n_trx
    return W


def port_mapping(n_trx: int, n_ports: int) -> np.ndarray:
    """TRX → CSI-RS 埠 的第二層映射,shape = (n_trx, n_ports)。

    n_ports == n_trx 時為單位矩陣。n_ports < n_trx 時把相鄰的 TRX 等權合併
    (再一次虛擬化;64T64R → 32 埠就是每 2 個垂直 TXRU 併成 1 埠)。
    """
    n_trx, n_ports = int(n_trx), int(n_ports)
    if n_ports <= 0 or n_ports == n_trx:
        return np.eye(n_trx, dtype=np.complex128)
    if n_trx % n_ports:
        raise ValueError(f"csi_ports={n_ports} 無法整除 trx_count={n_trx}")
    g = n_trx // n_ports
    W = np.zeros((n_trx, n_ports), dtype=np.complex128)
    for p in range(n_ports):
        W[p * g:(p + 1) * g, p] = 1.0 / np.sqrt(g)
    return W
