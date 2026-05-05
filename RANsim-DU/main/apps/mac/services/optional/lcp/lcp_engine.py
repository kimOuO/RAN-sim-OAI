"""Logical Channel Prioritization — 從多個 LCID 抽 SDU 拼出 TBS-bytes 的 MAC PDU。

對齊 3GPP TS 38.321 §5.4.3.1。簡化:按 5QI 數值小的優先,不做 PBR token bucket。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LcSdu:
    lcid: int
    qos_5qi: int
    bytes_available: int
    sdu_handle: object  # 真實對應 RLC entity 的 generate_pdu() callback,可放任何引用


def prioritize(scheduled_bytes: int, candidates: list[LcSdu]) -> list[tuple[LcSdu, int]]:
    """回傳 [(LcSdu, bytes_to_take), ...],總 bytes ≤ scheduled_bytes。"""
    if scheduled_bytes <= 0 or not candidates:
        return []
    sorted_cands = sorted(candidates, key=lambda c: c.qos_5qi)
    out: list[tuple[LcSdu, int]] = []
    remaining = scheduled_bytes
    for c in sorted_cands:
        if remaining <= 0:
            break
        take = min(c.bytes_available, remaining)
        if take > 0:
            out.append((c, take))
            remaining -= take
    return out
