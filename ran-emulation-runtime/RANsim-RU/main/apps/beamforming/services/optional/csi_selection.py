"""RI / PMI 選擇(模擬 UE 的 CSI 回報,TS 38.214 §5.2.2)。

真實的 UE 會對候選的 rank 與 PMI 逐一算等效 SINR,挑容量最大的回報。以前我們
DU 固定送 layers=1 / pmi=0,RU 只是拿未預編碼的 H 做 SVD 猜 rank,預編碼其實沒在動。

等效 SINR 的定義
----------------
`γ_ref` 是 RU 用 path_gain 算出的**每埠**參考 SINR(含跨 cell 干擾與雜訊)。
把通道正規化成「平均每埠每 rx 的功率 = 1」、預編碼矩陣總功率也正規化成 1
(trace(Wᴴ W) = 1),令 H_eff = H_norm · W,則第 i 層在 **MMSE 接收機**下的 SINR 為

    γ_i = 1 / [ (I + γ_ref · H_effᴴ H_eff)⁻¹ ]_ii  −  1

★ 一開始只用 γ_i = γ_ref·‖H_eff[:,i]‖²,那等於假設層與層之間完全不干擾。
  實測 2 埠 2rx 的純 LOS(通道其實只有 rank 1)會被選成 rank 2、兩層都「很好」——
  但兩層落在同一個空間特徵上,真實接收機根本分不開。MMSE 公式會自動把它壓下去。

驗算:
- SISO(1 埠 1 rx):H_norm = 1、W = [1] → γ_1 = γ_ref,與舊行為一致。
- 2 埠 LOS 同相、rank 1:W = [1;1]/√2 → ‖H W‖² = 2 → +3 dB,正是兩個 element 的
  波束成形增益(總發射功率固定,相干合成 N 倍)。32 埠則是 +10·log10(32) ≈ 15 dB。
- 同一條 rank-1 通道硬送 2 層:γ_i = γ/(1+γ) < 1,容量遠低於 rank 1 → 不會被選到。
這樣「天線變大 → SINR 變好」「通道撐不住就不會亂加層」才會真的出現在模擬裡。

搜尋策略(兩階段,對齊實作慣例)
--------------------------------
1. 先在 DFT 波束網格(N1·O1 × N2·O2,最多 256 個)上找最佳波束 i1_1 / i1_2:
   對兩個極化各算 ‖H_pol · v‖² 相加。一次矩陣乘法就算完。
2. 波束固定後,只窮舉 i1_3(第二道波束)與 i2(共相)以及各個 rank,精算容量
   Σ log2(1 + γ_i),取最大。候選數 ≲ 30。
"""
from __future__ import annotations

import numpy as np

from main.apps.beamforming.services.optional import codebook_type1 as cb


def normalize(H: np.ndarray) -> np.ndarray:
    """把 H 正規化成平均每個元素的功率 = 1(絕對準位由 γ_ref 帶)。"""
    p = float(np.mean(np.abs(H) ** 2))
    return H / np.sqrt(p) if p > 0 else H


def _beam_grid(n1: int, n2: int, o1: int, o2: int) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """所有候選 DFT 波束,回傳 (V: (N1·N2, n_beams), [(l,m), …])。"""
    idx = [(l, m) for l in range(n1 * o1) for m in range(n2 * o2)]
    V = np.column_stack([cb.dft_beam(n1, n2, l, m, o1, o2) for l, m in idx])
    return V, idx


_grid_cache: dict[tuple, tuple[np.ndarray, list[tuple[int, int]]]] = {}


def beam_grid(n1: int, n2: int, o1: int, o2: int):
    key = (n1, n2, o1, o2)
    if key not in _grid_cache:
        if len(_grid_cache) > 8:
            _grid_cache.clear()
        _grid_cache[key] = _beam_grid(n1, n2, o1, o2)
    return _grid_cache[key]


def best_beam(H_norm: np.ndarray, n1: int, n2: int, o1: int, o2: int) -> tuple[int, int, np.ndarray]:
    """第一階段:在波束網格上挑增益最大的 (l, m)。回傳 (l, m, 每道波束的增益)。"""
    V, idx = beam_grid(n1, n2, o1, o2)
    half = n1 * n2
    g = np.sum(np.abs(H_norm[:, :half] @ V) ** 2, axis=0) + np.sum(np.abs(H_norm[:, half:] @ V) ** 2, axis=0)
    b = int(np.argmax(g))
    return idx[b][0], idx[b][1], g


def layer_sinr(H_eff: np.ndarray, gamma_ref: float) -> np.ndarray:
    """MMSE 接收機下每層的 SINR(線性)。H_eff: (rx, layers)。"""
    L = H_eff.shape[1]
    G = H_eff.conj().T @ H_eff
    A = np.eye(L) + float(gamma_ref) * G
    try:
        d = np.real(np.diag(np.linalg.inv(A)))
    except np.linalg.LinAlgError:
        d = np.ones(L)
    return np.maximum(1.0 / np.maximum(d, 1e-12) - 1.0, 0.0)


def _capacity(sinr_lin: np.ndarray) -> float:
    return float(np.sum(np.log2(1.0 + np.maximum(sinr_lin, 0.0))))


def select(H: np.ndarray, *, gamma_ref_lin: float, layout: tuple[int, int] | None,
           max_rank: int = 4) -> dict:
    """挑 (rank, pmi)。H: (rx, ports) 未正規化的埠層通道。

    回傳 {rank, pmi, layer_sinr_lin(list), rank1_gain, capacity}。
    - `layer_sinr_lin`:選中的 (rank, pmi) 下每層的 MMSE SINR(線性,已含層間干擾)。
    - `rank1_gain`:最佳單層預編碼的陣列增益(線性),用來當這條鏈路的寬頻 SINR
      (γ_ref × rank1_gain),RLF / CQI 用它才會隨天線變大而改善。
    gamma_ref_lin ≤ 0(例如 SINR = −inf)時回 rank 1、pmi 0、增益 1。
    """
    if H.ndim != 2 or H.size == 0:
        return _fallback()
    n_rx, ports = H.shape
    max_rank = int(max(1, min(max_rank, n_rx, ports, 4)))
    if ports <= 1 or gamma_ref_lin <= 0:
        return _fallback()

    Hn = normalize(H)

    # 候選 PMI:2 埠或沒有 layout 就全窮舉(數量本來就小);否則兩階段。
    def _candidates(rank: int) -> list[int]:
        if layout is None or ports == 2:
            try:
                return list(range(cb.num_pmis(layers=rank, ports=ports)))
            except cb.CodebookError:
                return []
        n1, n2 = layout
        o1, o2 = cb.oversampling(n1, n2)
        l, m, _ = best_beam(Hn, n1, n2, o1, o2)
        base = (l * (n2 * o2) + m)
        n3 = cb.n_i13(n1, n2, rank)
        n_i2 = cb.n_i2(rank)
        return [(base * n3 + i3) * n_i2 + i2 for i3 in range(n3) for i2 in range(n_i2)]

    best = {"rank": 1, "pmi": 0, "layer_sinr_lin": [float(gamma_ref_lin)], "rank1_gain": 1.0, "capacity": -1.0}
    rank1_gain = 0.0
    for rank in range(1, max_rank + 1):
        for pmi in _candidates(rank):
            try:
                W = cb.precoder(pmi=pmi, layers=rank, ports=ports,
                                n1=layout[0] if layout else None, n2=layout[1] if layout else None)
            except cb.CodebookError:
                continue
            H_eff = Hn @ W
            if rank == 1:
                rank1_gain = max(rank1_gain, float(np.sum(np.abs(H_eff) ** 2)))
            g = layer_sinr(H_eff, gamma_ref_lin)
            c = _capacity(g)
            if c > best["capacity"]:
                best = {"rank": rank, "pmi": int(pmi), "layer_sinr_lin": [float(x) for x in g],
                        "rank1_gain": 0.0, "capacity": c}
    if best["capacity"] < 0:   # 全部失敗 → 退回單層
        return _fallback(gamma_ref_lin)
    best["rank1_gain"] = rank1_gain or 1.0
    return best


def _fallback(gamma_ref_lin: float = 1.0) -> dict:
    return {"rank": 1, "pmi": 0, "layer_sinr_lin": [float(max(gamma_ref_lin, 0.0))], "rank1_gain": 1.0, "capacity": 0.0}
