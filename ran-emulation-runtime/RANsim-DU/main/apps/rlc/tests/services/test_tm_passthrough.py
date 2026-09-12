from main.apps.rlc.services.optional.entities.tm_entity import TmEntity


def test_tm_passes_full_sdu():
    e = TmEntity()
    e.recv_sdu(50)
    assert e.buffer_status() == 50
    pdu = e.generate_pdu(50)
    assert pdu == 50
    assert e.buffer_status() == 0


def test_tm_partial_budget():
    e = TmEntity()
    e.recv_sdu(100)
    pdu1 = e.generate_pdu(40)
    assert pdu1 == 40
    pdu2 = e.generate_pdu(80)
    assert pdu2 == 60
    assert e.buffer_status() == 0
