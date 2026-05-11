"""SDU 切片 / PDU 重組。

對齊 OAI nr_rlc_oai_api.c 的 segmenter 行為,但不做位元級。
我們只算 byte-level 預算(MAC 給多少 bytes,RLC 從 SDU queue 拿出對應大小)。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class SduItem:
    sdu_id: int
    bytes_remaining: int  # 還沒被打包的 bytes
    delivered: bool = False
    enqueue_ts_ms: int = 0  # SDU 進 RLC tx queue 的時間戳（recv_sdu 設）


@dataclass
class SegmentResult:
    pdu_bytes: int
    consumed: list[tuple[int, int]]  # [(sdu_id, bytes_taken), ...]
    delivered_delay_ms: list[float] = field(default_factory=list)
    """這次 segment 完整投遞（剩 0 bytes）的 SDU 延遲（dequeue_ts - enqueue_ts）。
    對齊 3GPP TS 28.552 DRB.RlcSduDelayDl — RLC SDU 從進到出的時間。
    """


def segment(queue: list[SduItem], budget_bytes: int) -> SegmentResult:
    """從 queue 開頭取 SDU,湊滿 budget_bytes。

    剩下的 bytes 留在原 SduItem.bytes_remaining 中,等下個 PDU 繼續。
    完整 deliver 的 SDU 計算 delay 並回傳。
    """
    if budget_bytes <= 0:
        return SegmentResult(pdu_bytes=0, consumed=[])

    now_ms = _now_ms()
    used = 0
    consumed: list[tuple[int, int]] = []
    delivered_delays: list[float] = []
    for item in queue:
        if item.bytes_remaining <= 0:
            continue
        take = min(item.bytes_remaining, budget_bytes - used)
        if take <= 0:
            break
        item.bytes_remaining -= take
        if item.bytes_remaining == 0:
            item.delivered = True
            if item.enqueue_ts_ms:
                delivered_delays.append(float(now_ms - item.enqueue_ts_ms))
        consumed.append((item.sdu_id, take))
        used += take
        if used >= budget_bytes:
            break
    # purge delivered items
    queue[:] = [x for x in queue if not x.delivered]
    return SegmentResult(
        pdu_bytes=used, consumed=consumed, delivered_delay_ms=delivered_delays,
    )


def total_buffer_bytes(queue: Iterable[SduItem]) -> int:
    return sum(x.bytes_remaining for x in queue if not x.delivered)
