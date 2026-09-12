"""Per-DRB PDCP entity (simplified).

OAI ref: openair2/LAYER2/nr_pdcp/nr_pdcp_entity.c.
We model only sequence numbering and packet counts. Ciphering / integrity are
no-op stubs — the prompt explicitly puts AES out of scope.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class PdcpPdu:
    sn: int
    payload: bytes


class PdcpEntity:
    """Per (ue_id, drb_id) entity. Thread-safe at a coarse lock granularity."""

    def __init__(self, ue_id: str, drb_id: int, sn_size: int = 12) -> None:
        self.ue_id = ue_id
        self.drb_id = drb_id
        self._sn_modulus = 1 << sn_size  # 4096 by default (NR PDCP SN)
        self._tx_sn = 0
        self._rx_next = 0
        self._lock = threading.Lock()

    # Tx (DL): SDAP → PDCP → GTP-U F1-U
    def add_sdu(self, sdu: bytes) -> PdcpPdu:
        with self._lock:
            sn = self._tx_sn
            self._tx_sn = (self._tx_sn + 1) % self._sn_modulus
        return PdcpPdu(sn=sn, payload=sdu)

    # Rx (UL): GTP-U F1-U → PDCP → SDAP
    def receive_pdu(self, pdu: PdcpPdu) -> bytes:
        with self._lock:
            self._rx_next = (pdu.sn + 1) % self._sn_modulus
        return pdu.payload

    @property
    def tx_sn(self) -> int:
        return self._tx_sn

    @property
    def rx_next(self) -> int:
        return self._rx_next


# Process-local registry (mirrors OAI's nr_pdcp_ue_manager singleton)
_REGISTRY: dict[tuple[str, int], PdcpEntity] = {}
_REG_LOCK = threading.Lock()


def get_or_create_entity(ue_id: str, drb_id: int) -> PdcpEntity:
    key = (ue_id, drb_id)
    with _REG_LOCK:
        if key not in _REGISTRY:
            _REGISTRY[key] = PdcpEntity(ue_id, drb_id)
        return _REGISTRY[key]


def remove_entity(ue_id: str, drb_id: int) -> None:
    with _REG_LOCK:
        _REGISTRY.pop((ue_id, drb_id), None)


def reset_all() -> None:
    with _REG_LOCK:
        _REGISTRY.clear()
