"""UlRrcDispatcher 純邏輯測試 — 不需 HTTP / Django DB。"""
import base64
from unittest.mock import patch

import pytest

from main.apps.f1ap_du.services.optional.ul_rrc.ul_rrc_dispatcher import UlRrcDispatcher


def test_to_b64_from_bytes():
    raw = b"\x00\x01RRCSetupRequest\xff"
    out = UlRrcDispatcher.to_b64(raw)
    assert base64.b64decode(out) == raw


def test_to_b64_from_valid_b64_string_passes_through():
    b64 = base64.b64encode(b"abc").decode()
    assert UlRrcDispatcher.to_b64(b64) == b64


def test_to_b64_invalid_string_raises():
    with pytest.raises(ValueError, match="invalid base64"):
        UlRrcDispatcher.to_b64("@@@not_base64!!!")


def test_to_b64_unsupported_type_raises():
    with pytest.raises(TypeError):
        UlRrcDispatcher.to_b64(12345)  # type: ignore[arg-type]


def test_dispatch_empty_ue_id_raises():
    with pytest.raises(ValueError):
        UlRrcDispatcher.dispatch("", b"x")


def test_dispatch_calls_cu_client_with_correct_payload():
    with patch(
        "main.apps.f1ap_du.services.optional.ul_rrc.ul_rrc_dispatcher.CuClientBusinessService.post_ul_rrc_message",
        return_value=True,
    ) as mock_post:
        ok = UlRrcDispatcher.dispatch("ue-7", b"hello")
    assert ok is True
    args, kwargs = mock_post.call_args
    payload = args[0]
    assert payload["ue_id"] == "ue-7"
    assert base64.b64decode(payload["rrc_msg_b64"]) == b"hello"


def test_dispatch_returns_false_when_cu_unreachable():
    with patch(
        "main.apps.f1ap_du.services.optional.ul_rrc.ul_rrc_dispatcher.CuClientBusinessService.post_ul_rrc_message",
        return_value=False,
    ):
        assert UlRrcDispatcher.dispatch("ue-7", b"x") is False
