"""Mock GTP-U tunnel manager.

OAI ref: openair3/ocp-gtpu/gtp_itf.cpp (newGtpuCreateTunnel at L657).

We do not run real UDP/2152 packets; we maintain ``te2ue_mapping`` and
``ue2te_mapping`` semantics in process memory so that PDCP / SDAP can resolve
where to forward, and we count packets per DRB via the Drb model.
"""
from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass


@dataclass
class TunnelEndpoint:
    """One side of a GTP-U tunnel. Mirrors gtpv1u_bearer_t."""

    ue_id: str
    drb_id: int
    local_teid: int       # we receive on this TEID
    peer_teid: int = 0    # we send to peer on this TEID (0 = unknown yet)
    peer_addr: str = ""
    peer_port: int = 2152


class GtpuTunnel:
    """Per-instance tunnel registry. There are two instances at CU-UP:
    one for N3 (toward UPF), one for F1-U (toward DU). The instance kind
    is implicit via callers — the registry is unified.
    """

    _teid_seq = itertools.count(start=1)
    _registry_by_teid: dict[int, TunnelEndpoint] = {}
    _registry_by_drb: dict[tuple[str, int, str], TunnelEndpoint] = {}
    _lock = threading.Lock()

    @classmethod
    def _next_teid(cls) -> int:
        with cls._lock:
            return next(cls._teid_seq)

    @classmethod
    def create_tunnel(
        cls,
        ue_id: str,
        drb_id: int,
        kind: str,
        peer_addr: str = "",
        peer_teid: int = 0,
    ) -> TunnelEndpoint:
        local_teid = cls._next_teid()
        ep = TunnelEndpoint(
            ue_id=ue_id, drb_id=drb_id,
            local_teid=local_teid,
            peer_teid=peer_teid, peer_addr=peer_addr,
        )
        with cls._lock:
            cls._registry_by_teid[local_teid] = ep
            cls._registry_by_drb[(ue_id, drb_id, kind)] = ep
        return ep

    @classmethod
    def get_by_teid(cls, teid: int) -> TunnelEndpoint | None:
        with cls._lock:
            return cls._registry_by_teid.get(teid)

    @classmethod
    def get_by_drb(cls, ue_id: str, drb_id: int, kind: str) -> TunnelEndpoint | None:
        with cls._lock:
            return cls._registry_by_drb.get((ue_id, drb_id, kind))

    @classmethod
    def update_peer(
        cls, ue_id: str, drb_id: int, kind: str,
        peer_addr: str, peer_teid: int,
    ) -> None:
        ep = cls.get_by_drb(ue_id, drb_id, kind)
        if ep is None:
            return
        with cls._lock:
            ep.peer_addr = peer_addr
            ep.peer_teid = peer_teid

    @classmethod
    def remove_for_ue(cls, ue_id: str) -> None:
        with cls._lock:
            stale = [k for k in cls._registry_by_drb if k[0] == ue_id]
            for k in stale:
                ep = cls._registry_by_drb.pop(k)
                cls._registry_by_teid.pop(ep.local_teid, None)

    @classmethod
    def reset_all(cls) -> None:
        with cls._lock:
            cls._registry_by_drb.clear()
            cls._registry_by_teid.clear()
            cls._teid_seq = itertools.count(start=1)
