"""NR-ARFCN ↔ 頻率換算(TS 38.104 §5.4.2.1)。

為什麼需要:UE 量測鄰區時真實看得到的是 PCI 與載波頻率(以 ARFCN 表示),
而 DU 的 CellState 只存 freq_ghz。對外要給 ARFCN 就得換算。

換算表(Table 5.4.2.1-1):
    0–3000 MHz      ΔF_global 5 kHz    F_offs 0 MHz      N_offs 0
    3000–24250 MHz  ΔF_global 15 kHz   F_offs 3000 MHz   N_offs 600000
    24250–100000MHz ΔF_global 60 kHz   F_offs 24250.08MHz N_offs 2016667

驗證方式:走廊場景 registry 設 3.5 GHz / arfcn 633333,本函式算出來要一致
(600000 + 500000/15 = 633333)。對不上就是公式用錯,馬上看得出來。
"""
from __future__ import annotations

# (頻率下界 MHz, ΔF_global kHz, F_REF-Offs MHz, N_REF-Offs)
_BANDS = (
    (0.0, 5.0, 0.0, 0),
    (3000.0, 15.0, 3000.0, 600000),
    (24250.0, 60.0, 24250.08, 2016667),
)


def nr_arfcn_from_mhz(f_mhz: float) -> int | None:
    """載波中心頻率(MHz)→ NR-ARFCN。超出定義範圍回 None(不猜)。"""
    if f_mhz is None or f_mhz <= 0 or f_mhz > 100000.0:
        return None
    lo, dsc, f_offs, n_offs = _BANDS[0]
    for b in _BANDS:
        if f_mhz >= b[0]:
            lo, dsc, f_offs, n_offs = b
    return int(n_offs + round((f_mhz - f_offs) * 1000.0 / dsc))


def nr_arfcn_from_ghz(f_ghz: float | None) -> int | None:
    return None if f_ghz is None else nr_arfcn_from_mhz(float(f_ghz) * 1000.0)
