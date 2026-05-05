"""RLC AM — 12-bit SN + segment + ARQ + status PDU。

對齊 OAI nr_rlc_entity_am.c。簡化:retx queue 用 SN 重排序;status PDU 帶 ACK_SN + 1 個 NACK list。
"""
from __future__ import annotations

from dataclasses import dataclass

from main.apps.rlc.services.optional.segmentation.segmenter import SduItem, segment, total_buffer_bytes

AM_HEADER_BYTES = 3  # 簡化:固定 3-byte (D/C + P + SI + SN12)
STATUS_PDU_BASE_BYTES = 4
MAX_RETX = 4


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

    def recv_sdu(self, n_bytes: int) -> int:
        sid = self._next_sdu_id
        self._next_sdu_id += 1
        self._tx_queue.append(SduItem(sdu_id=sid, bytes_remaining=n_bytes))
        return sid

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
