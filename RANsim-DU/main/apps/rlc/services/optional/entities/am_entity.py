"""RLC AM — 12-bit SN + segment + ARQ + status PDU。

對齊 OAI nr_rlc_entity_am.c。簡化:retx queue 用 SN 重排序;status PDU 帶 ACK_SN + 1 個 NACK list。
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from main.apps.rlc.services.optional.segmentation.segmenter import SduItem, segment, total_buffer_bytes
from main.utils.env_loader import get_int


def _now_ms() -> int:
    return int(time.time() * 1000)

AM_HEADER_BYTES = 3  # 簡化:固定 3-byte (D/C + P + SI + SN12)
STATUS_PDU_BASE_BYTES = 4
MAX_RETX = 4

# AK10 — RLC AM tx buffer 上限（bytes），對齊 OAI nr_rlc_entity_am.c:1842-1847 的
# tx_maxsize check at recv_sdu。OAI 預設 50 MB（RLC_TX_MAXSIZE × 5），對 macro
# 真機跑高 MCS 是 1 秒級 buffer；sim 環境通常被 SINR 限制在低 MCS（25 kbps drain），
# 50 MB 會撐出小時級 delay。我們改 default 100 KB，達 cap 後 reject 新進 SDU
# （非 head-drop；對應 OAI 行為），count 進 tx_dropped_sdus / tx_dropped_bytes
# 給 KPM。值可以用 RLC_TX_MAXSIZE_BYTES 環境變數 override。
#
# delay 數學：steady-state queue 會撐到 cap → average wait ≈ cap_bytes × 8 / (2 × drain_bps)
# - drain 25 kbps + cap 100 KB → avg ~16 s（仍偏大但比無限好）
# - drain 50 Mbps + cap 100 KB → avg ~8 ms（合理）
# 想壓到 ms 級可以用 RLC_TX_MAXSIZE_BYTES=2048 等。
TX_MAXSIZE_BYTES = get_int("RLC_TX_MAXSIZE_BYTES", 100_000)


@dataclass
class TxBlock:
    sn: int
    bytes: int
    retx_count: int = 0
    acked: bool = False


class AmEntity:
    mode = "AM"

    def __init__(self, sn_field_length: int = 12) -> None:
        self.sn_field_length = sn_field_length
        self._sn_max = (1 << sn_field_length) - 1
        self._tx_queue: list[SduItem] = []          # 還未組成 PDU 的 SDU
        self._tx_window: list[TxBlock] = []          # 已送出、等 ACK 的 PDU
        self._next_sdu_id = 0
        self._next_sn = 0
        self.retx_count = 0
        self._status_pending = False
        self._rx: list[SduItem] = []
        self._delay_samples_ms: list[float] = []     # 累計 SDU delivery delay，take_delay_samples() 取出後清空
        # AK10 — running tx buffer 估算（避免每次 recv_sdu 都 O(n) 掃 _tx_queue）
        # 跟 segment() 同步：segment 從 _tx_queue 消費 bytes 後也要扣，但 segment 不
        # 知道這個欄位 → 維持「entry/exit 各一次的近似量」就好，掃描 fallback 由
        # buffer_status() 提供 truth。
        self._tx_buffer_bytes_est: int = 0
        # AK10 — cap 觸發的 drop 計數，PM aggregator 透過 take_drop_samples() 取走
        self._dropped_sdus_pending: int = 0
        self._dropped_bytes_pending: int = 0
        self.tx_dropped_sdus_total: int = 0
        self.tx_dropped_bytes_total: int = 0

    def recv_sdu(self, n_bytes: int, enqueue_ts_ms: int | None = None) -> int:
        # AL: caller (e.g. inject_sdu_batch) 若提供 per-packet ts 就用 caller 給的,
        # 否則 fallback wall-clock now — 對齊 OAI per-packet enqueue 時序.
        # AK10: 對齊 OAI nr_rlc_entity_am.c:1842-1847 — cap 滿了 reject 新 SDU
        # 而不是丟既存 queue head。tx_dropped_* 計數給 PM aggregator 收集成
        # DRB.PdcpSduDropDl-like 指標（之後可接 KPM）。
        current_bytes = total_buffer_bytes(self._tx_queue)
        if current_bytes + n_bytes > TX_MAXSIZE_BYTES:
            self._dropped_sdus_pending += 1
            self._dropped_bytes_pending += n_bytes
            self.tx_dropped_sdus_total += 1
            self.tx_dropped_bytes_total += n_bytes
            return -1  # sentinel: caller can choose to treat as drop
        sid = self._next_sdu_id
        self._next_sdu_id += 1
        ts = enqueue_ts_ms if enqueue_ts_ms is not None else _now_ms()
        self._tx_queue.append(SduItem(sdu_id=sid, bytes_remaining=n_bytes, enqueue_ts_ms=ts))
        return sid

    def take_drop_samples(self) -> tuple[int, int]:
        """Return (dropped_sdus, dropped_bytes) since last call, then reset window.

        AK10: PM aggregator 每 tick 撈一次，累計進 _UeWindowAccumulator 後 flush 成
        DRB.PdcpSduDropDl bytes / count 提供 e2adapter KPM。"""
        s, b = self._dropped_sdus_pending, self._dropped_bytes_pending
        self._dropped_sdus_pending = 0
        self._dropped_bytes_pending = 0
        return s, b

    def take_delay_samples(self) -> list[float]:
        """返回近期 segment 的 HoL delay (ms) 列表，並清空 buffer。

        對齊 3GPP TS 28.552 DRB.RlcSduDelayDl — Tick driver 每 N tick 收一次。
        """
        samples = self._delay_samples_ms
        self._delay_samples_ms = []
        return samples

    def generate_pdu(self, budget_bytes: int) -> int:
        # retx 優先
        for blk in self._tx_window:
            if blk.acked:
                continue
            if blk.retx_count == 0:
                continue  # 還在等 ACK,不算 retx
            if budget_bytes >= blk.bytes + AM_HEADER_BYTES:
                # 重發
                blk.retx_count += 1
                return blk.bytes + AM_HEADER_BYTES
        # 新傳
        if budget_bytes <= AM_HEADER_BYTES:
            return 0
        payload_budget = budget_bytes - AM_HEADER_BYTES
        seg = segment(self._tx_queue, payload_budget)
        if seg.pdu_bytes <= 0:
            return 0
        sn = self._next_sn
        self._next_sn = (self._next_sn + 1) & self._sn_max
        self._tx_window.append(TxBlock(sn=sn, bytes=seg.pdu_bytes))
        # HoL delay sample for this segment call (對齊 3GPP TS 28.552)
        if seg.delivered_delay_ms:
            self._delay_samples_ms.extend(seg.delivered_delay_ms)
        return seg.pdu_bytes + AM_HEADER_BYTES

    def recv_pdu(self, n_bytes: int) -> None:
        if n_bytes <= AM_HEADER_BYTES:
            return
        payload = n_bytes - AM_HEADER_BYTES
        self._rx.append(SduItem(sdu_id=self._next_sdu_id, bytes_remaining=payload))
        self._next_sdu_id += 1
        # 模擬:每收 N 個 PDU 觸發一次 status PDU
        if len(self._rx) % 4 == 0:
            self._status_pending = True

    def handle_ack(self, sn: int, success: bool) -> None:
        for blk in self._tx_window:
            if blk.sn != sn:
                continue
            if success:
                blk.acked = True
                self.retx_count = max(0, self.retx_count - blk.retx_count)
            else:
                blk.retx_count += 1
                self.retx_count += 1
                if blk.retx_count >= MAX_RETX:
                    blk.acked = True  # 強制丟棄
            break
        self._tx_window = [b for b in self._tx_window if not b.acked]

    def buffer_status(self) -> int:
        new_bo = total_buffer_bytes(self._tx_queue)
        retx_bo = sum(b.bytes for b in self._tx_window if not b.acked and b.retx_count > 0)
        if new_bo == 0 and retx_bo == 0:
            return 0
        return new_bo + retx_bo + AM_HEADER_BYTES

    def status_report(self) -> int:
        """回傳 status PDU 的 byte size(簡化)。"""
        if not self._status_pending:
            return 0
        self._status_pending = False
        return STATUS_PDU_BASE_BYTES
