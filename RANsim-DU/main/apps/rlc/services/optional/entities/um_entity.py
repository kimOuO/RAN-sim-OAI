"""RLC UM — segment、無 ARQ。對齊 OAI nr_rlc_entity_um.c。"""
from __future__ import annotations

from main.apps.rlc.services.optional.segmentation.segmenter import SduItem, segment, total_buffer_bytes

UM_HEADER_BYTES = 2  # 簡化:2-byte header (SN + SI)


class UmEntity:
    mode = "UM"

    def __init__(self, sn_field_length: int = 12) -> None:
        self.sn_field_length = sn_field_length
        self._tx: list[SduItem] = []
        self._rx: list[SduItem] = []
        self._next_sdu_id = 0

    def recv_sdu(self, n_bytes: int) -> int:
        sid = self._next_sdu_id
        self._next_sdu_id += 1
        self._tx.append(SduItem(sdu_id=sid, bytes_remaining=n_bytes))
        return sid

    def generate_pdu(self, budget_bytes: int) -> int:
        if budget_bytes <= UM_HEADER_BYTES:
            return 0
        payload_budget = budget_bytes - UM_HEADER_BYTES
        return segment(self._tx, payload_budget).pdu_bytes + UM_HEADER_BYTES

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
