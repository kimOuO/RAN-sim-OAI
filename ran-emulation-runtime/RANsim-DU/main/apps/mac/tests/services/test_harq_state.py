from main.apps.mac.services.optional.harq.harq_manager import HarqManager, MAX_RETX


def test_acquire_then_ack_to_done():
    m = HarqManager()
    m.add_ue("ue1")
    p = m.acquire_process("ue1", "DL", tbs_bytes=1500)
    assert p.state == "WAIT_FEEDBACK"
    final = m.handle_feedback("ue1", p.pid, "DL", success=True)
    assert final.state == "DONE"


def test_nack_goes_retx_then_eventually_done():
    m = HarqManager()
    p = m.acquire_process("ue1", "UL", tbs_bytes=800)
    pid = p.pid
    for _ in range(MAX_RETX - 1):
        st = m.handle_feedback("ue1", pid, "UL", success=False)
        assert st.state == "RETX"
    st = m.handle_feedback("ue1", pid, "UL", success=False)
    assert st.state == "DONE"  # 達 MAX_RETX 強制 DONE


def test_invalid_pid_returns_none():
    m = HarqManager()
    m.add_ue("ue1")
    assert m.handle_feedback("ue1", harq_pid=999, direction="DL", success=True) is None
