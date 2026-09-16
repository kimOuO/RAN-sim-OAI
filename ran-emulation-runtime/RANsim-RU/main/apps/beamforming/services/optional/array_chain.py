"""元件 → CSI-RS 埠 的完整映射鏈(有快取)。

物理(Sionna)回來的 H 是 **元件層**:(num_rx_ant, n_elem)。
DU 的 PMI / rank 講的是 **埠層**。中間差兩層:

    H_port = H_elem · W_virt · P_port
             └ virtualization.build()   (n_elem × n_trx)   TR 38.901 式 (7.3-1)
                                └ virtualization.port_mapping()  (n_trx × n_ports)

本模組把兩個矩陣乘好並依設定簽章快取(陣列設定很少變,但每 tick 每 UE 都要用)。
"""
from __future__ import annotations

import threading
from typing import Any

import numpy as np

from main.apps.beamforming.services.optional import codebook_type1, virtualization

_lock = threading.Lock()
_cache: dict[tuple, dict[str, Any]] = {}
_CACHE_MAX = 8


def signature(cfg: Any, etilt: float | None = None) -> tuple:
    """AntennaConfig(或任何有同名屬性的物件)→ 快取鍵。

    etilt 不為 None 時覆寫電子下傾(B2:per-cell 的 RIC 控制值疊在 preset 預設值之上)。
    """
    g = lambda k, d=0: getattr(cfg, k, d)  # noqa: E731
    _tilt = float(g("electrical_tilt_deg", 0.0)) if etilt is None else float(etilt)
    return (int(g("rows", 1)), int(g("cols", 1)), str(g("polarization", "V")),
            int(g("panels_mg", 1)), int(g("panels_ng", 1)),
            int(g("trx_v_group", 1)), int(g("trx_count", 0)), _tilt,
            int(g("csi_ports", 0)), int(g("port_n1", 0)), int(g("port_n2", 0)),
            float(g("vertical_spacing", 0.5)), str(g("ru_category", "A")))


def _derive(sig: tuple) -> dict[str, Any]:
    (rows, cols, pol, mg, ng, v_group, trx_declared, etilt, ports_declared, n1, n2, v_sp, cat) = sig

    n_elem = virtualization.element_count(rows=rows, cols=cols, polarization=pol, panels_mg=mg, panels_ng=ng)
    W_virt = virtualization.build(rows=rows, cols=cols, polarization=pol, panels_mg=mg, panels_ng=ng,
                                  v_group=v_group, v_spacing=v_sp, electrical_tilt_deg=etilt)
    n_trx = W_virt.shape[1]
    if trx_declared and trx_declared != n_trx:
        # 設定不一致時以幾何推算為準(preset 的 trx_count 只是宣告值)
        pass

    n_ports = int(ports_declared) or n_trx
    if n_ports > n_trx:
        n_ports = n_trx
    P_port = virtualization.port_mapping(n_trx, n_ports)
    chain = W_virt @ P_port

    # (N1,N2):優先用 preset 宣告的;沒宣告就依埠數取 TS 38.214 表的預設組合
    layout: tuple[int, int] | None = None
    if n1 and n2 and 2 * n1 * n2 == n_ports:
        layout = (int(n1), int(n2))
    elif n_ports in codebook_type1.PORT_LAYOUTS and n_ports > 2:
        layout = codebook_type1.default_layout(n_ports)

    return {"chain": chain, "n_elem": n_elem, "n_trx": n_trx, "n_ports": n_ports,
            "layout": layout, "ru_category": cat}


def get(cfg: Any, etilt: float | None = None) -> dict[str, Any]:
    """回傳 {chain, n_elem, n_trx, n_ports, layout, ru_category}。"""
    sig = signature(cfg, etilt)
    with _lock:
        hit = _cache.get(sig)
        if hit is not None:
            return hit
    built = _derive(sig)
    with _lock:
        if len(_cache) >= _CACHE_MAX:
            _cache.clear()
        _cache[sig] = built
    return built


def to_ports(H_elem: np.ndarray, cfg: Any, etilt: float | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    """H(rx, n_elem) → H(rx, n_ports)。元件數對不上就原樣回傳(舊 cache / 舊 physics)。"""
    info = get(cfg, etilt)
    chain = info["chain"]
    if H_elem.ndim != 2 or H_elem.shape[1] != chain.shape[0]:
        return H_elem, {**info, "applied": False}
    return H_elem @ chain, {**info, "applied": True}
