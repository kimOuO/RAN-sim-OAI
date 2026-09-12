"""PDCP sequence number behaviour."""
from __future__ import annotations

from main.apps.cu_up.services.optional.pdcp.pdcp_entity import (
    PdcpEntity, PdcpPdu, get_or_create_entity, reset_all,
)


def setup_function(_):
    reset_all()


def test_tx_sn_monotonic():
    e = PdcpEntity("ue-1", drb_id=1)
    p1 = e.add_sdu(b"hi")
    p2 = e.add_sdu(b"hi")
    assert p1.sn == 0
    assert p2.sn == 1


def test_tx_sn_wraps_at_modulus():
    e = PdcpEntity("ue-1", drb_id=1, sn_size=4)  # modulus 16
    last = None
    for _ in range(17):
        last = e.add_sdu(b"x")
    assert last is not None
    assert last.sn == 0  # wrapped


def test_singleton_per_ue_drb():
    a = get_or_create_entity("ue-1", 1)
    b = get_or_create_entity("ue-1", 1)
    c = get_or_create_entity("ue-1", 2)
    assert a is b
    assert a is not c
