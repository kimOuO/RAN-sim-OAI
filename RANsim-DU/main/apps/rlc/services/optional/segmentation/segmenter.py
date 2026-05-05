"""SDU 切片 / PDU 重組。

對齊 OAI nr_rlc_oai_api.c 的 segmenter 行為,但不做位元級。
我們只算 byte-level 預算(MAC 給多少 bytes,RLC 從 SDU queue 拿出對應大小)。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class SduItem:
    sdu_id: int
    bytes_remaining: int  # 還沒被打包的 bytes
    delivered: bool = False


@dataclass
class SegmentResult:
    pdu_bytes: int
    consumed: list[tuple[int, int]]  # [(sdu_id, bytes_taken), ...]


def segment(queue: list[SduItem], budget_bytes: int) -> SegmentResult:
    """從 queue 開頭取 SDU,湊滿 budget_bytes。

    剩下的 bytes 留在原 SduItem.bytes_remaining 中,等下個 PDU 繼續。
    """
    if budget_bytes <= 0:
        return SegmentResult(pdu_bytes=0, consumed=[])

    used = 0
    consumed: list[tuple[int, int]] = []
    for item in queue:
        if item.bytes_remaining <= 0:
            continue
        take = min(item.bytes_remaining, budget_bytes - used)
        if take <= 0:
            break
        item.bytes_remaining -= take
        if item.bytes_remaining == 0:
            item.delivered = True
        consumed.append((item.sdu_id, take))
        used += take
        if used >= budget_bytes:
            break
    # purge delivered items
    queue[:] = [x for x in queue if not x.delivered]
    return SegmentResult(pdu_bytes=used, consumed=consumed)


def total_buffer_bytes(queue: Iterable[SduItem]) -> int:
    return sum(x.bytes_remaining for x in queue if not x.delivered)
