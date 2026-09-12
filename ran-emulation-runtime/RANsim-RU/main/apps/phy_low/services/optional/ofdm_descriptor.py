"""OFDM grid 結構描述 — numerology / SCS / FFT size 查表（不算真 IQ）。

3GPP TS 38.211 §5.3.1, §5.3.2。
對 OAI: openair1/PHY/MODULATION/ofdm_mod.c 的參數面，不重做運算。
"""
from __future__ import annotations


# numerology μ → SCS (kHz), symbols/slot, slots/subframe
_NUMEROLOGY_TABLE = {
    0: {"scs_khz": 15,   "symbols_per_slot": 14, "slots_per_subframe": 1},
    1: {"scs_khz": 30,   "symbols_per_slot": 14, "slots_per_subframe": 2},
    2: {"scs_khz": 60,   "symbols_per_slot": 14, "slots_per_subframe": 4},
    3: {"scs_khz": 120,  "symbols_per_slot": 14, "slots_per_subframe": 8},
    4: {"scs_khz": 240,  "symbols_per_slot": 14, "slots_per_subframe": 16},
}


# 常見 BW (MHz) → 大致 FFT size（基於 30 kHz SCS 的 PRB 數）
_FFT_GUIDE = {
    20: 1024,
    50: 1536,
    100: 4096,
    200: 8192,
    400: 16384,
}


class OfdmDescriptorError(ValueError):
    pass


def describe_ofdm(numerology: int, *, bandwidth_mhz: float = 100.0, cp_type: str = "normal") -> dict:
    info = _NUMEROLOGY_TABLE.get(numerology)
    if info is None:
        raise OfdmDescriptorError(f"unsupported numerology {numerology}")

    fft_size = _FFT_GUIDE.get(int(bandwidth_mhz), 4096)
    return {
        "numerology": numerology,
        "scs_khz": info["scs_khz"],
        "symbols_per_slot": info["symbols_per_slot"],
        "slots_per_subframe": info["slots_per_subframe"],
        "slots_per_frame": info["slots_per_subframe"] * 10,
        "fft_size": fft_size,
        "cp_type": cp_type,
        "bandwidth_mhz": bandwidth_mhz,
    }
