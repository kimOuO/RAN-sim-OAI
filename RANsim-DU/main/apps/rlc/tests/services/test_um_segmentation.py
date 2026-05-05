from main.apps.rlc.services.optional.entities.um_entity import UM_HEADER_BYTES, UmEntity


def test_um_includes_header():
    e = UmEntity()
    e.recv_sdu(50)
    pdu = e.generate_pdu(60)
    assert pdu == 50 + UM_HEADER_BYTES


def test_um_zero_when_budget_too_small():
    e = UmEntity()
    e.recv_sdu(50)
    assert e.generate_pdu(UM_HEADER_BYTES) == 0


def test_um_buffer_status_includes_header_when_nonempty():
    e = UmEntity()
    assert e.buffer_status() == 0
    e.recv_sdu(20)
    assert e.buffer_status() == 20 + UM_HEADER_BYTES
