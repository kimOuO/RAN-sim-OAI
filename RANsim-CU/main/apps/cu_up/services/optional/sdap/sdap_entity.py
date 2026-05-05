"""SDAP entity — QoS-Flow ↔ DRB mapping.

OAI ref: openair2/SDAP/nr_sdap/nr_sdap_entity.c (nr_sdap_tx_entity at L81).
"""
from __future__ import annotations

import threading


class SdapEntity:
    """Per-UE SDAP. Holds qfi → drb mapping.

    For DL data, prepend 1-byte SDAP header carrying QFI; for UL strip it.
    Real OAI varies header presence by config — here we always include it.
    """

    def __init__(self, ue_id: str) -> None:
        self.ue_id = ue_id
        self._qfi_to_drb: dict[int, int] = {}
        self._default_drb: int | None = None
        self._lock = threading.Lock()

    def map_qfi(self, qfi: int, drb_id: int, *, default: bool = False) -> None:
        with self._lock:
            self._qfi_to_drb[qfi] = drb_id
            if default or self._default_drb is None:
                self._default_drb = drb_id

    def lookup_drb(self, qfi: int) -> int | None:
        with self._lock:
            return self._qfi_to_drb.get(qfi, self._default_drb)

    def add_dl_header(self, payload: bytes, qfi: int, rqi: bool = False) -> bytes:
        # 1-byte DL SDAP header: bit7 RDI(0), bit6 RQI, bits5..0 QFI
        hdr = ((1 if rqi else 0) << 6) | (qfi & 0x3F)
        return bytes([hdr]) + payload

    def strip_ul_header(self, payload: bytes) -> tuple[int, bytes]:
        if not payload:
            return 0, payload
        qfi = payload[0] & 0x3F
        return qfi, payload[1:]


_REGISTRY: dict[str, SdapEntity] = {}
_REG_LOCK = threading.Lock()


def get_or_create(ue_id: str) -> SdapEntity:
    with _REG_LOCK:
        if ue_id not in _REGISTRY:
            _REGISTRY[ue_id] = SdapEntity(ue_id)
        return _REGISTRY[ue_id]


def remove(ue_id: str) -> None:
    with _REG_LOCK:
        _REGISTRY.pop(ue_id, None)


def reset_all() -> None:
    with _REG_LOCK:
        _REGISTRY.clear()
