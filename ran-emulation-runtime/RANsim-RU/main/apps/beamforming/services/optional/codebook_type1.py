"""TS 38.214 §5.2.2.2.1 Type I 單面板 codebook(參數化產生,非查表)。

跟 `codebook.py` 的差別:
- `codebook.py` 是 **TS 38.211 §6.3.1.5 的 PUSCH precoding 表**(照抄 OAI),只有 2 / 4 埠。
- 本模組是 **下行 CSI 的 Type I 單面板 codebook**,埠數 = 2·N1·N2,涵蓋 4–32 埠。
  PMI/RI 回報講的是這一個,所以 DL 預編碼應該用這裡。

結構 W = W1 · W2:
  W1 = DFT 波束群(GoB 的數學本體)
       u_m   = [1, e^{j2πm/(O2·N2)}, …, e^{j2πm(N2−1)/(O2·N2)}]                 長度 N2
       v_lm  = [u_m, e^{j2πl/(O1·N1)}·u_m, …, e^{j2πl(N1−1)/(O1·N1)}·u_m]        長度 N1·N2
  W2 = 選波束 + 兩個極化之間的共相 φ_n = e^{jπn/2}

rank 1(Table 5.2.2.2.1-5):W = (1/√(2·N1·N2))·[v_lm ; φ_n·v_lm],n = i2 ∈ {0,1,2,3}
rank 2:                   W = (1/√(2·2·N1·N2))·[v_lm  v_l'm' ; φ_n·v_lm  −φ_n·v_l'm'],n ∈ {0,1}
rank 3/4:在 rank 2 的兩道正交波束上再疊 ± 共相(對應 P_CSI-RS < 16 的結構)。
  ★ rank 1/2 的 W 與規格式子一致;rank ≥ 2 的第二道波束偏移 (k1,k2) 不照
    Table 5.2.2.2.1-3 逐格抄,改由 (N1,N2) 推出保證正交且不繞回的組合(見 beam_offsets)。

2 埠(N1=N2=1)不走 DFT 結構,直接用 Table 5.2.2.2.1-1 的專用表。

PMI 打平成單一整數(對外 API 與舊 codebook 一致):
    ports == 2 : pmi = i2
    其餘       : pmi = ((i1_1·(N2·O2) + i1_2)·n_i13 + i1_3)·n_i2 + i2
"""
from __future__ import annotations

import numpy as np

# 過取樣因子:TS 38.214 Table 5.2.2.2.1-2。N2 == 1 時 O2 = 1。
_O1_DEFAULT = 4
_O2_DEFAULT = 4

# TS 38.214 Table 5.2.2.2.1-2:埠數 → 允許的 (N1, N2)
PORT_LAYOUTS: dict[int, tuple[tuple[int, int], ...]] = {
    2: ((1, 1),),
    4: ((2, 1),),
    8: ((2, 2), (4, 1)),
    12: ((3, 2), (6, 1)),
    16: ((4, 2), (8, 1)),
    24: ((4, 3), (6, 2), (12, 1)),
    32: ((4, 4), (8, 2), (16, 1)),
}


class CodebookError(ValueError):
    """不支援的 (ports, layers, pmi) 組合。"""


def oversampling(n1: int, n2: int) -> tuple[int, int]:
    """(O1, O2);N2 == 1 時 O2 = 1(Table 5.2.2.2.1-2)。"""
    return (_O1_DEFAULT, _O2_DEFAULT if int(n2) > 1 else 1)


def default_layout(ports: int) -> tuple[int, int]:
    """埠數 → 預設 (N1, N2):取表上第一組(較方正的排列)。"""
    opts = PORT_LAYOUTS.get(int(ports))
    if not opts:
        raise CodebookError(f"TS 38.214 Type I 不支援 {ports} 埠(允許 {sorted(PORT_LAYOUTS)})")
    return opts[0]


def dft_beam(n1: int, n2: int, l: int, m: int, o1: int | None = None, o2: int | None = None) -> np.ndarray:
    """v_{l,m},長度 N1·N2。這也是 GoB 裡「一道波束」的權重向量。"""
    n1, n2 = int(n1), int(n2)
    if o1 is None or o2 is None:
        o1, o2 = oversampling(n1, n2)
    u = np.exp(2j * np.pi * int(m) * np.arange(n2) / (o2 * n2))
    phases = np.exp(2j * np.pi * int(l) * np.arange(n1) / (o1 * n1))
    return np.concatenate([p * u for p in phases])


def beam_offsets(n1: int, n2: int, o1: int, o2: int) -> list[tuple[int, int]]:
    """rank ≥ 2 第二道波束的候選偏移 (k1, k2)。

    兩道 DFT 波束正交的條件是索引差為 O 的非零倍數,且必須落在過取樣網格
    [0, O1·N1) / [0, O2·N2) 內不繞回:k1 = a·O1(a = 1…N1−1)、k2 = b·O2(b = 1…N2−1)。
    ★ 2026-09-16 實測:照 Table 5.2.2.2.1-3 字面用 (2O1,0)…(4O1,0),在 N1 = 2 時
      2·O1 ≡ 0 (mod N1·O1),第二道波束會退化成第一道,rank 3/4 的層間就不正交。
      這裡改成由 (N1,N2) 推出保證不繞回的組合,再取前 4 個(對齊規格的 i1_3 ≤ 2 bit)。
    """
    n1, n2 = int(n1), int(n2)
    out: list[tuple[int, int]] = [(a * o1, 0) for a in range(1, n1)]
    out += [(0, b * o2) for b in range(1, n2)]
    out += [(a * o1, b * o2) for a in range(1, n1) for b in range(1, n2)]
    return (out or [(0, 0)])[:4]


def _beam_pair_offset(n1: int, n2: int, i13: int, o1: int, o2: int) -> tuple[int, int]:
    offs = beam_offsets(n1, n2, o1, o2)
    return offs[int(i13) % len(offs)]


def n_i13(n1: int, n2: int, layers: int) -> int:
    """rank ≥ 2 時第二道波束的候選數;rank 1 不需要。"""
    if int(layers) < 2:
        return 1
    o1, o2 = oversampling(n1, n2)
    return len(beam_offsets(n1, n2, o1, o2))


def n_i2(layers: int) -> int:
    """共相候選數:rank 1 有 4 個(1, j, −1, −j),rank ≥ 2 只有 2 個(1, j)。"""
    return 4 if int(layers) == 1 else 2


# ── 2 埠專用表(TS 38.214 Table 5.2.2.2.1-1)────────────────────────────────
_W_2PORT_R1 = [np.array([[1.0 + 0j], [c]]) / np.sqrt(2) for c in (1, 1j, -1, -1j)]
_W_2PORT_R2 = [
    np.array([[1.0 + 0j, 1.0 + 0j], [1.0 + 0j, -1.0 + 0j]]) / 2.0,
    np.array([[1.0 + 0j, 1.0 + 0j], [1j, -1j]]) / 2.0,
]


def num_pmis(*, layers: int, ports: int, n1: int | None = None, n2: int | None = None) -> int:
    """這個 (ports, layers) 底下合法的 PMI 個數。"""
    ports, layers = int(ports), int(layers)
    if ports == 2:
        if layers == 1:
            return len(_W_2PORT_R1)
        if layers == 2:
            return len(_W_2PORT_R2)
        raise CodebookError(f"2 埠只支援 rank 1–2,不支援 rank {layers}")
    if n1 is None or n2 is None:
        n1, n2 = default_layout(ports)
    if 2 * n1 * n2 != ports:
        raise CodebookError(f"(N1,N2)=({n1},{n2}) 對應 {2 * n1 * n2} 埠,與 ports={ports} 不符")
    if not 1 <= layers <= 4:
        raise CodebookError(f"本實作支援 rank 1–4,不支援 rank {layers}")
    o1, o2 = oversampling(n1, n2)
    return (n1 * o1) * (n2 * o2) * n_i13(n1, n2, layers) * n_i2(layers)


def decode_pmi(pmi: int, *, layers: int, ports: int, n1: int | None = None, n2: int | None = None) -> dict:
    """打平的 PMI → (i1_1, i1_2, i1_3, i2)。除錯與 KPM 回報用。"""
    ports, layers = int(ports), int(layers)
    if ports == 2:
        return {"i1_1": 0, "i1_2": 0, "i1_3": 0, "i2": int(pmi)}
    if n1 is None or n2 is None:
        n1, n2 = default_layout(ports)
    o1, o2 = oversampling(n1, n2)
    n3, n2_i2 = n_i13(n1, n2, layers), n_i2(layers)
    i2 = pmi % n2_i2
    rest = pmi // n2_i2
    i13 = rest % n3
    rest //= n3
    i12 = rest % (n2 * o2)
    i11 = rest // (n2 * o2)
    return {"i1_1": int(i11), "i1_2": int(i12), "i1_3": int(i13), "i2": int(i2)}


def precoder(*, pmi: int, layers: int, ports: int, n1: int | None = None, n2: int | None = None) -> np.ndarray:
    """回傳 W,shape = (ports, layers),**已含 1/√(layers·ports) 正規化**。

    注意:與舊的 `codebook.lookup()` 不同,本函式回傳的 W 已正規化,
    呼叫端不要再乘一次(見 precoder.apply_pmi 的分支)。
    """
    ports, layers, pmi = int(ports), int(layers), int(pmi)
    total = num_pmis(layers=layers, ports=ports, n1=n1, n2=n2)
    if not 0 <= pmi < total:
        raise CodebookError(f"pmi={pmi} 超出範圍(ports={ports} rank={layers} 共 {total} 個)")

    if ports == 2:
        return (_W_2PORT_R1 if layers == 1 else _W_2PORT_R2)[pmi].copy()

    if n1 is None or n2 is None:
        n1, n2 = default_layout(ports)
    o1, o2 = oversampling(n1, n2)
    idx = decode_pmi(pmi, layers=layers, ports=ports, n1=n1, n2=n2)
    phi = np.exp(1j * np.pi * idx["i2"] / 2.0)
    v = dft_beam(n1, n2, idx["i1_1"], idx["i1_2"], o1, o2)

    if layers == 1:
        W = np.concatenate([v, phi * v]).reshape(-1, 1)
    else:
        k1, k2 = _beam_pair_offset(n1, n2, idx["i1_3"], o1, o2)
        v2 = dft_beam(n1, n2, idx["i1_1"] + k1, idx["i1_2"] + k2, o1, o2)
        top = {2: [v, v2], 3: [v, v2, v], 4: [v, v2, v, v2]}[layers]
        bot = {2: [phi * v, -phi * v2],
               3: [phi * v, phi * v2, -phi * v],
               4: [phi * v, phi * v2, -phi * v, -phi * v2]}[layers]
        W = np.vstack([np.column_stack(top), np.column_stack(bot)])

    return W / np.sqrt(layers * ports)


def selftest() -> dict:
    """基本性質檢查:形狀、行正交、功率正規化。"""
    out: dict[str, object] = {"checked": [], "errors": []}
    for ports in (2, 4, 8, 16, 32):
        n1, n2 = default_layout(ports)
        for layers in (1, 2, 3, 4):
            if ports == 2 and layers > 2:
                continue
            try:
                total = num_pmis(layers=layers, ports=ports, n1=n1, n2=n2)
                for pmi in (0, total // 2, total - 1):
                    W = precoder(pmi=pmi, layers=layers, ports=ports, n1=n1, n2=n2)
                    if W.shape != (ports, layers):
                        out["errors"].append(f"{ports}p r{layers} pmi{pmi}: shape {W.shape}")
                    p = float(np.real(np.trace(W.conj().T @ W)))
                    if abs(p - 1.0) > 1e-9:
                        out["errors"].append(f"{ports}p r{layers} pmi{pmi}: 總功率 {p:.6f} != 1")
                    if layers > 1:
                        g = W.conj().T @ W
                        off = float(np.max(np.abs(g - np.diag(np.diag(g)))))
                        if off > 1e-9:
                            out["errors"].append(f"{ports}p r{layers} pmi{pmi}: 層間不正交 {off:.2e}")
                out["checked"].append(f"{ports}p r{layers} ({total} PMI)")
            except CodebookError as exc:
                out["errors"].append(f"{ports}p r{layers}: {exc}")
    return out
