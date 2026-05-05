"""Layer mapping — 純抽象(不做 codeword 切割)。

對齊 3GPP TS 38.211 §7.3.1.3:DL 最多 4 layer (single CW) 或 8 layer (dual CW)。
"""
from __future__ import annotations


def split_payload_per_layer(total_bytes: int, num_layers: int) -> list[int]:
    if num_layers <= 0:
        return [total_bytes]
    base = total_bytes // num_layers
    remainder = total_bytes - base * num_layers
    return [base + (1 if i < remainder else 0) for i in range(num_layers)]
