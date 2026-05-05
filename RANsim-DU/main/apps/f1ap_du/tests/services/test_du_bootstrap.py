"""du_bootstrap 純邏輯測試 — 不需 HTTP / 完整 Django app loading。"""
from main.apps.f1ap_du.services.optional.lifecycle.du_bootstrap import (
    BootstrapState,
    _parse_setup_response,
    get_state,
    reset_state,
)


def test_initial_state_is_init():
    reset_state()
    s = get_state()
    assert s.state == "INIT"
    assert s.transaction_id == 0
    assert s.attempts == 0
    assert s.last_response is None


def test_parse_wrapped_response_accepted():
    body = {"status": "success", "data": {"accepted": True, "transaction_id": 42}}
    accepted, tid = _parse_setup_response(body)
    assert accepted is True
    assert tid == 42


def test_parse_wrapped_response_rejected():
    body = {"status": "success", "data": {"accepted": False, "transaction_id": 99}}
    accepted, tid = _parse_setup_response(body)
    assert accepted is False
    assert tid == 99


def test_parse_bare_response():
    """CU 直接送 dataclass 序列化(非 RANsim 包裝格式)也要吃。"""
    body = {"accepted": True, "transaction_id": 7}
    accepted, tid = _parse_setup_response(body)
    assert accepted is True
    assert tid == 7


def test_parse_missing_fields_defaults_to_false():
    body = {"status": "success", "data": {}}
    accepted, tid = _parse_setup_response(body)
    assert accepted is False
    assert tid == 0


def test_parse_garbage_body():
    assert _parse_setup_response("not a dict") == (False, 0)  # type: ignore[arg-type]
    assert _parse_setup_response({"data": "not a dict"}) == (False, 0)


def test_parse_handles_string_transaction_id_gracefully():
    body = {"data": {"accepted": True, "transaction_id": "garbage"}}
    accepted, tid = _parse_setup_response(body)
    assert accepted is True
    assert tid == 0


def test_bootstrap_state_dataclass_default():
    s = BootstrapState()
    assert s.state == "INIT"
    assert s.attempts == 0
