"""Grid of Beams(GoB)—— O-RAN Cat B「predefined-beam」用的波束集合。

O-RAN WG4 CUS-plane 的四種 beamforming 方法裡,predefined-beam 是:
O-RU 開機時經 M-plane 公告自己有哪些波束,之後 O-DU 每個 section 只帶一個 `beamId`。
本模組就是「O-RU 手上那份波束表」。

波束本體是 TS 38.214 Type I 的 DFT 波束 v_{l,m}(codebook_type1.dft_beam),
差別只在:codebook 是 UE 回報 PMI 去選,GoB 是 O-RU 自己存一份固定的子集、由 beamId 指定。

座標與索引約定(與 virtualization.py 一致)
------------------------------------------
埠層的索引順序是 `pol → 面板 → 欄(水平) → 垂直群`,垂直最快。對應到 38.214:
    N1 = 水平(欄數),N2 = 垂直(垂直群數)
所以 v_{l,m} 的 l 掃方位、m 掃仰角。

指向角
------
相位遞增 Δφ = 2π·l/(O1·N1) 對應到波束指向 θ:2π·d·sin θ = Δφ,故

    sin(方位) = − l' / (O1·N1·d_h_eff)
    sin(仰角) = − m' / (O2·N2·d_v_eff)

負號來自匹配濾波:對指向 a 的通道 h_c = exp(+j2π·d·c·sin a),最佳權重是 w_c = conj(h_c),
而 v_{l,m} 的相位是 **+**2π·l·c/(O1·N1),所以 v_l 實際指向 sin a = −l'/(O1·N1·d)。
(2026-09-16 實測:不加負號時,把 UE 放在 −60° 會選到標示 +61° 的波束。)

l' / m' 是把 [0, O·N) 折到以正面為中心的對稱區間([-ON/2, ON/2))。
d_*_eff 是**埠與埠之間**的等效間距,不是元件間距:一個 TXRU 垂直吃掉 `trx_v_group`
片元件、埠映射再合併 `merge` 個 TXRU,所以 d_v_eff = d_v × trx_v_group × merge。
(大子陣列會讓 d_v_eff ≫ λ/2 而出現柵瓣,這是真實 mMIMO 面板本來就有的性質;
 掃描範圍因此變窄。超出 ±90° 的候選標 steerable=False,間距 > 0.5λ 的標 grating=True ——
 後者指向角有歧義:2026-09-16 用理想 steering vector 實測,d_v=3.2λ 時 −8° 的入射會選到
 標示 +8.99° 的波束,因為那道波束的柵瓣正好落在 −8.99°。實際通道裡子陣列自己的元件方向圖
 會壓掉柵瓣,所以這個歧義只在「不含元件方向圖的理想測試」才顯現。)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from main.apps.beamforming.services.optional import codebook_type1 as cb


@dataclass
class Beam:
    beam_id: int
    l: int
    m: int
    azimuth_deg: float          # 相對陣列正面,正 = 右
    elevation_deg: float        # 相對陣列正面,正 = 上
    steerable: bool = True      # sin 超過 1 → 該索引在這個間距下指不到
    grating: bool = False       # 埠間距 > 0.5λ → 可視區內有柵瓣,指向角有歧義
    weights: np.ndarray = field(default=None, repr=False)   # (ports, 1) rank-1 權重


def _folded(i: int, n: int) -> int:
    """把 [0, n) 折到以 0 為中心的對稱區間 [-n/2, n/2)。"""
    return i - n if i >= (n + 1) // 2 else i


def _angle_deg(idx: int, total: int, spacing: float) -> tuple[float, bool]:
    if spacing <= 0 or total <= 0:
        return 0.0, True
    s = -_folded(idx, total) / (total * spacing)
    if abs(s) > 1.0:
        return math.copysign(90.0, s), False
    return math.degrees(math.asin(s)), True


def rank1_weights(n1: int, n2: int, l: int, m: int, o1: int, o2: int) -> np.ndarray:
    """一道波束的 rank-1 權重(兩個極化同相),shape = (2·N1·N2, 1),總功率 1。"""
    v = cb.dft_beam(n1, n2, l, m, o1, o2)
    w = np.concatenate([v, v]).reshape(-1, 1)
    return w / np.sqrt(2.0 * n1 * n2 * 2.0)


def rank2_weights(n1: int, n2: int, l: int, m: int, o1: int, o2: int) -> np.ndarray:
    """同一道波束上用雙極化送 2 層(mMIMO 做 SU-MIMO 的標準作法),shape = (ports, 2)。"""
    v = cb.dft_beam(n1, n2, l, m, o1, o2)
    W = np.vstack([np.column_stack([v, v]), np.column_stack([v, -v])])
    return W / np.sqrt(2.0 * 2.0 * n1 * n2 * 2.0)


def build(*, n1: int, n2: int, az_beams: int = 0, el_beams: int = 0,
          d_h: float = 0.5, d_v: float = 0.5,
          o1: int | None = None, o2: int | None = None) -> list[Beam]:
    """產生 GoB。az_beams / el_beams = 0 時取正交波束數(各 N1 / N2 道)。"""
    n1, n2 = int(n1), int(n2)
    if o1 is None or o2 is None:
        o1, o2 = cb.oversampling(n1, n2)
    tot_l, tot_m = n1 * o1, n2 * o2
    n_az = int(az_beams) or n1
    n_el = int(el_beams) or n2
    n_az, n_el = max(1, min(n_az, tot_l)), max(1, min(n_el, tot_m))
    # 在過取樣網格上等距取樣(先折到對稱區間再排序,讓 beam_id 依角度由小到大)
    ls = sorted({int(round(i * tot_l / n_az)) % tot_l for i in range(n_az)}, key=lambda x: _folded(x, tot_l))
    ms = sorted({int(round(i * tot_m / n_el)) % tot_m for i in range(n_el)}, key=lambda x: _folded(x, tot_m))

    beams: list[Beam] = []
    bid = 0
    for m in ms:
        for l in ls:
            az, ok_a = _angle_deg(l, tot_l, d_h)
            el, ok_e = _angle_deg(m, tot_m, d_v)
            beams.append(Beam(beam_id=bid, l=l, m=m, azimuth_deg=round(az, 2),
                              elevation_deg=round(el, 2), steerable=bool(ok_a and ok_e),
                              grating=bool(d_h > 0.5 or d_v > 0.5),
                              weights=rank1_weights(n1, n2, l, m, o1, o2)))
            bid += 1
    return beams


def effective_spacing(cfg: Any, chain_info: dict) -> tuple[float, float]:
    """埠與埠之間的等效間距 (d_h_eff, d_v_eff),單位 λ。"""
    g = lambda k, d: getattr(cfg, k, d)  # noqa: E731
    d_h = float(g("horizontal_spacing", 0.5))
    d_v = float(g("vertical_spacing", 0.5))
    v_group = max(1, int(g("trx_v_group", 1)))
    n_trx = int(chain_info.get("n_trx") or 1)
    n_ports = int(chain_info.get("n_ports") or n_trx)
    merge = max(1, n_trx // max(1, n_ports))
    return d_h, d_v * v_group * merge


_cache: dict[tuple, list[Beam]] = {}


def for_config(cfg: Any, chain_info: dict) -> list[Beam]:
    """依 AntennaConfig + chain 資訊取得 GoB(有快取)。沒有 layout 就回空表。"""
    layout = chain_info.get("layout")
    if not layout:
        return []
    n1, n2 = layout
    d_h, d_v = effective_spacing(cfg, chain_info)
    az = int(getattr(cfg, "gob_az_beams", 0) or 0)
    el = int(getattr(cfg, "gob_el_beams", 0) or 0)
    key = (n1, n2, az, el, round(d_h, 4), round(d_v, 4))
    if key not in _cache:
        if len(_cache) > 8:
            _cache.clear()
        _cache[key] = build(n1=n1, n2=n2, az_beams=az, el_beams=el, d_h=d_h, d_v=d_v)
    return _cache[key]


def select(H_port: np.ndarray, beams: list[Beam], *, top_k: int = 3) -> dict:
    """在 GoB 裡挑最佳波束。H_port: (rx, ports)。

    回傳 {beam_id, gain, top: [(beam_id, 相對增益 dB), …]}。
    「相對增益」是相對最佳波束的 dB 差,給 RIC 的 per-beam RSRP 統計用
    (O-RAN WG1 §4.6.4.1 要每波束 RSRP)。
    """
    if H_port.ndim != 2 or not beams:
        return {"beam_id": None, "gain": 0.0, "top": []}
    W = np.hstack([b.weights for b in beams])          # (ports, n_beams)
    g = np.sum(np.abs(H_port @ W) ** 2, axis=0)        # 每道波束的接收功率
    order = np.argsort(g)[::-1]
    best = int(order[0])
    g_best = float(g[best]) or 1e-30
    top = [(int(beams[i].beam_id), round(10.0 * math.log10(max(float(g[i]), 1e-30) / g_best), 2))
           for i in order[:max(1, top_k)]]
    return {"beam_id": int(beams[best].beam_id), "gain": float(g[best]), "top": top,
            "azimuth_deg": beams[best].azimuth_deg, "elevation_deg": beams[best].elevation_deg}
