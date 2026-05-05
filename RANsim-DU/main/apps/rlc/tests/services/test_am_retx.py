from main.apps.rlc.services.optional.entities.am_entity import AM_HEADER_BYTES, AmEntity


def test_am_first_pdu():
    e = AmEntity()
    e.recv_sdu(50)
    pdu = e.generate_pdu(100)
    assert pdu == 50 + AM_HEADER_BYTES


def test_am_ack_clears_window():
    e = AmEntity()
    e.recv_sdu(40)
    e.generate_pdu(100)
    e.handle_ack(0, success=True)
    assert e.buffer_status() == 0


def test_am_nack_triggers_retx():
    e = AmEntity()
    e.recv_sdu(40)
    e.generate_pdu(100)
    e.handle_ack(0, success=False)
    assert e.retx_count >= 1
    pdu = e.generate_pdu(100)
    assert pdu > 0
