from main.apps.mac.services.optional.random_access.ra_manager import RaManager


def test_msg1_assigns_tc_rnti():
    m = RaManager()
    s1 = m.msg1_detected("ue1", ts_ms=1000)
    s2 = m.msg1_detected("ue2", ts_ms=1001)
    assert s1.tc_rnti != s2.tc_rnti
    assert s1.state == "MSG1_DETECTED"


def test_advance_and_finalize():
    m = RaManager()
    m.msg1_detected("ue1", ts_ms=1000)
    m.advance("ue1", "MSG2_SENT")
    m.advance("ue1", "WAIT_MSG3")
    m.advance("ue1", "MSG4_SENT")
    m.finalize("ue1")
    assert all(s.ue_id != "ue1" for s in m.in_progress())
