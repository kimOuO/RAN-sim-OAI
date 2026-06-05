"""RLC UM — segment、無 ARQ。對齊 OAI nr_rlc_entity_um.c。"""
from __future__ import annotations

import time

from main.apps.rlc.services.optional.segmentation.segmenter import SduItem, segment, total_buffer_bytes
from main.utils.env_loader import get_bool

UM_HEADER_BYTES = 2  # 簡化:2-byte header (SN + SI)

# 改動一 shadow:on 時才旁路收集 (arrival_sim_ms, bytes);off 時零成本
# takeover 也要收(否則只開 takeover 不開 shadow → slot 引擎吃不到 SDU → delay KPM 歸零,code-review #1)
_SLOT_ENGINE_SHADOW = get_bool("SLOT_ENGINE_SHADOW", False) or get_bool("SLOT_ENGINE_TAKEOVER", False)


def _now_ms() -> int:
    return int(time.time() * 1000)


class UmEntity:
    mode = "UM"

    def __init__(self, sn_field_length: int = 12) -> None:
        self.sn_field_length = sn_field_length
        self._tx: list[SduItem] = []
        self._rx: list[SduItem] = []
        self._next_sdu_id = 0
        self._delay_samples_ms: list[float] = []
        self._sdu_arrivals_shadow: list[tuple[float, int]] = []  # 改動一 shadow
        self._server_free_sim_ms: float = 0.0  # P0b subtick FIFO 伺服器游標

    def recv_sdu(self, n_bytes: int, enqueue_ts_ms: int | None = None,
                 arrival_sim_ms: float = 0.0) -> int:
        # AL: caller (e.g. inject_sdu_batch) 若提供 per-packet ts 就用 caller 給的,
        # 否則 fallback wall-clock now — 對齊 OAI per-packet enqueue 時序.
        sid = self._next_sdu_id
        self._next_sdu_id += 1
        ts = enqueue_ts_ms if enqueue_ts_ms is not None else _now_ms()
        self._tx.append(SduItem(
            sdu_id=sid, bytes_remaining=n_bytes, enqueue_ts_ms=ts,
            arrival_sim_ms=arrival_sim_ms,
        ))
        if _SLOT_ENGINE_SHADOW:
            self._sdu_arrivals_shadow.append((arrival_sim_ms, n_bytes))
        return sid

    def take_delay_samples(self) -> list[float]:
        samples = self._delay_samples_ms
        self._delay_samples_ms = []
        return samples

    def take_sdu_arrivals(self) -> list[tuple[float, int]]:
        """改動一 shadow:回傳本 tick 到達的 (arrival_sim_ms, bytes) 並清空。"""
        a = self._sdu_arrivals_shadow
        self._sdu_arrivals_shadow = []
        return a

    def generate_pdu(self, budget_bytes: int, *, subtick: bool = False,
                     rate_bytes_per_sim_ms: float = 0.0, now_sim_ms: float = 0.0) -> int:
        if budget_bytes <= UM_HEADER_BYTES:
            return 0
        payload_budget = budget_bytes - UM_HEADER_BYTES
        seg = segment(
            self._tx, payload_budget,
            subtick=subtick, rate_bytes_per_sim_ms=rate_bytes_per_sim_ms,
            server_free_sim_ms=self._server_free_sim_ms, now_sim_ms=now_sim_ms,
        )
        self._server_free_sim_ms = seg.server_free_sim_ms
        if seg.delivered_delay_ms:
            self._delay_samples_ms.extend(seg.delivered_delay_ms)
        return seg.pdu_bytes + UM_HEADER_BYTES

    def recv_pdu(self, n_bytes: int) -> None:
        if n_bytes <= UM_HEADER_BYTES:
            return
        payload = n_bytes - UM_HEADER_BYTES
        self._rx.append(SduItem(sdu_id=self._next_sdu_id, bytes_remaining=payload))
        self._next_sdu_id += 1

    def buffer_status(self) -> int:
        bo = total_buffer_bytes(self._tx)
        return bo + UM_HEADER_BYTES if bo > 0 else 0

    def status_report(self) -> bytes:
        return b""
