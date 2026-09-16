"""由「路徑參數」重建元件層通道 H(階段 C,2026-09-17)。

cached 模式以前只存每 (tick, UE, cell) 一個 path gain,所以永遠 rank 1、沒有波束。
現在預算時用 1×1、雙極化 VH 的陣列跑 Sionna,每條路徑存:

    A_k   (2, 2) complex   [rx_pol(V,H), tx_pol(V,H)] 單一元件的係數(已含元件方向圖)
    k_t,k (3,)             離開方向單位向量(Sionna 座標)
    k_r,k (3,)             到達方向單位向量

RU 依當下的天線設定組回元件層 H,公式與 Sionna synthetic array 相同
(sionna/rt/path_solvers/paths.py `_apply_synthetic_array`):

    H[r, t] = Σ_k  c(ζ_r)ᵀ · A_k · c(ζ_t) · exp(j2π·(R_r·p_r)·k_r,k) · exp(j2π·(R_t·p_t)·k_t,k) · φ_k

- p 是以 λ 為單位的元件位置;PlanarArray:y = d_h·col − (N−1)·d_h/2、z = −d_v·row + (M−1)·d_v/2
- R = Rz(α)·Ry(β)·Rx(γ)(TR 38.901 式 7.1-4,與 sionna.rt.utils.rotation_matrix 相同)
- c(ζ) = (cos ζ, sin ζ):polarization model tr38901_2 對斜角線性,
  所以 V(0°)、H(90°)、cross(±45°)都能由 V/H 兩個分量組出來
- φ_k:每條路徑的隨機相位(與 live 模式的 fast fading 同義)
- 元件順序與 Sionna / virtualization.py 一致:pol 慢 → 面板 → col → row 快
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

_SLANTS = {"v": (0.0,), "h": (90.0,), "vh": (0.0, 90.0), "cross": (-45.0, 45.0), "dual": (-45.0, 45.0)}


def slant_angles(polarization: str) -> tuple[float, ...]:
    return _SLANTS.get(str(polarization or "V").lower(), (0.0,))


def rotation_matrix(alpha: float, beta: float, gamma: float) -> np.ndarray:
    sa, ca = math.sin(alpha), math.cos(alpha)
    sb, cb = math.sin(beta), math.cos(beta)
    sc, cc = math.sin(gamma), math.cos(gamma)
    return np.array([
        [ca * cb, ca * sb * sc - sa * cc, ca * sb * cc + sa * sc],
        [sa * cb, sa * sb * sc + ca * cc, sa * sb * cc - ca * sc],
        [-sb, cb * sc, cb * cc],
    ])


@lru_cache(maxsize=32)
def element_positions(rows: int, cols: int, d_v: float = 0.5, d_h: float = 0.5,
                      panels_mg: int = 1, panels_ng: int = 1,
                      panel_v: float = 0.0, panel_h: float = 0.0) -> np.ndarray:
    """(n_pos, 3) 元件位置(λ),單一極化的順序:面板 → col → row。

    多面板依 TR 38.901 §7.3:面板中心間距 d_g,V / d_g,H(λ);沒給就緊貼(= 面板尺寸 + 一個元件間距)。
    """
    M, N, Mg, Ng = int(rows), int(cols), int(panels_mg), int(panels_ng)
    pv = float(panel_v) or M * d_v
    ph = float(panel_h) or N * d_h
    out = []
    for pm in range(Mg):
        for pn in range(Ng):
            oy = (pn - (Ng - 1) / 2.0) * ph
            oz = -(pm - (Mg - 1) / 2.0) * pv
            for c in range(N):
                for r in range(M):
                    out.append((0.0, d_h * c - (N - 1) * d_h / 2.0 + oy, -d_v * r + (M - 1) * d_v / 2.0 + oz))
    arr = np.array(out, dtype=np.float64)
    arr.setflags(write=False)
    return arr


def _array_terms(pos: np.ndarray, slants: tuple[float, ...], R: np.ndarray, k: np.ndarray):
    """回傳 (pol_vec (n_elem, 2), phase (n_elem, K)),元件順序 pol 慢。"""
    rp = pos @ R.T                                   # (n_pos, 3)
    ph = np.exp(2j * np.pi * (rp @ k.T))             # (n_pos, K)
    pol = np.array([[math.cos(math.radians(z)), math.sin(math.radians(z))] for z in slants])
    n = len(pos)
    return np.repeat(pol, n, axis=0), np.tile(ph, (len(slants), 1))


def synthesize(A: np.ndarray, k_t: np.ndarray, k_r: np.ndarray, *,
               tx: dict, rx: dict, tx_orientation=(0.0, 0.0, 0.0), rx_orientation=(0.0, 0.0, 0.0),
               fading: bool = True, rng: np.random.Generator | None = None) -> np.ndarray:
    """A: (K, 2, 2)、k_t / k_r: (K, 3) → H: (n_rx_elem, n_tx_elem) complex。

    tx / rx 是陣列設定 dict(rows, cols, polarization, vertical_spacing, horizontal_spacing,
    panels_mg, panels_ng, panel_v_spacing, panel_h_spacing;缺的用預設)。
    """
    A = np.asarray(A, dtype=np.complex128)
    live = np.any(A != 0, axis=(1, 2))
    if not np.any(live):
        return np.zeros((element_count(rx), element_count(tx)), dtype=np.complex128)
    A, k_t, k_r = A[live], np.asarray(k_t, float)[live], np.asarray(k_r, float)[live]
    if fading:
        rng = rng or np.random.default_rng()
        A = A * np.exp(2j * np.pi * rng.random(len(A)))[:, None, None]

    def _terms(cfg, orient, k):
        pos = element_positions(int(cfg.get("rows", 1)), int(cfg.get("cols", 1)),
                                float(cfg.get("vertical_spacing", 0.5)), float(cfg.get("horizontal_spacing", 0.5)),
                                int(cfg.get("panels_mg", 1)), int(cfg.get("panels_ng", 1)),
                                float(cfg.get("panel_v_spacing", 0.0) or 0.0), float(cfg.get("panel_h_spacing", 0.0) or 0.0))
        return _array_terms(pos, slant_angles(cfg.get("polarization", "V")), rotation_matrix(*orient), k)

    pt, ft = _terms(tx, tx_orientation, k_t)        # (T, 2), (T, K)
    pr, fr = _terms(rx, rx_orientation, k_r)        # (R, 2), (R, K)
    # 極化耦合:g[r, t, k] = pr[r]ᵀ · A_k · pt[t]
    g = np.einsum("ri,kij,tj->rtk", pr, A, pt)
    return np.einsum("rtk,rk,tk->rt", g, fr, ft)


def element_count(cfg: dict) -> int:
    return (int(cfg.get("panels_mg", 1)) * int(cfg.get("panels_ng", 1)) * int(cfg.get("rows", 1))
            * int(cfg.get("cols", 1)) * len(slant_angles(cfg.get("polarization", "V"))))
