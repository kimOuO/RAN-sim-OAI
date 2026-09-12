"""Y1: E2 Reset Request encoder + send-debounce unit tests.

Y1 fixes the case where sim CU restart wipes its in-memory subscription
registry but RIC keeps cached sub_id. Without Reset, indications get silently
dropped by RIC for ever. With Reset, RIC clears state and re-issues SUB_REQ.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from main.apps.e2_adapter.services.optional.codec import e2ap_codec
from main.apps.e2_adapter.services.optional.sctp_link import sctp_loop


class E2ResetEncoderTests(TestCase):
    def test_encode_reset_round_trip(self) -> None:
        """Encoded Reset Request decodes to procCode=3 with TransactionID + Cause."""
        encoded = e2ap_codec.encode_e2_reset_request(cause_misc="om-intervention")
        self.assertGreater(len(encoded), 0)

        decoded = e2ap_codec.decode_e2ap_pdu(encoded)
        outer_choice, inner = decoded
        self.assertEqual(outer_choice, "initiatingMessage")
        self.assertEqual(inner["procedureCode"], 3)  # id-Reset
        self.assertEqual(inner["value"][0], "ResetRequest")

        ies = inner["value"][1]["protocolIEs"]
        ie_ids = [ie["id"] for ie in ies]
        self.assertIn(49, ie_ids)  # TransactionID
        self.assertIn(1, ie_ids)   # Cause

        cause_ie = next(ie for ie in ies if ie["id"] == 1)
        self.assertEqual(cause_ie["value"][1], ("misc", "om-intervention"))


class E2ResetSendDebounceTests(TestCase):
    def setUp(self) -> None:
        sctp_loop._LAST_RESET_SENT_MS = 0

    def test_first_reset_sends_subsequent_debounced(self) -> None:
        """Reset 30s 內第二次呼叫應被 debounce, 第一次成功."""
        sent_pdus: list[bytes] = []

        def fake_send_sctp(sock, data, ppid=70) -> bool:
            sent_pdus.append(data)
            return True

        with patch.object(sctp_loop, "_send_sctp", side_effect=fake_send_sctp):
            ok1 = sctp_loop._send_e2_reset(sock=None, reason="test1")
            ok2 = sctp_loop._send_e2_reset(sock=None, reason="test2")

        self.assertTrue(ok1)
        self.assertFalse(ok2)
        self.assertEqual(len(sent_pdus), 1)

    def test_reset_after_cooldown_window(self) -> None:
        """超過 cooldown 後可以再送一次."""
        sent_pdus: list[bytes] = []

        def fake_send_sctp(sock, data, ppid=70) -> bool:
            sent_pdus.append(data)
            return True

        with patch.object(sctp_loop, "_send_sctp", side_effect=fake_send_sctp):
            self.assertTrue(sctp_loop._send_e2_reset(sock=None, reason="t1"))
            sctp_loop._LAST_RESET_SENT_MS -= sctp_loop._RESET_COOLDOWN_MS + 1
            self.assertTrue(sctp_loop._send_e2_reset(sock=None, reason="t2"))

        self.assertEqual(len(sent_pdus), 2)

    def test_send_failure_does_not_arm_cooldown(self) -> None:
        """SCTP send 失敗時不該 arm cooldown — 下次 SubNotFound 還能再嘗試."""
        with patch.object(sctp_loop, "_send_sctp", return_value=False):
            ok = sctp_loop._send_e2_reset(sock=None, reason="fail")

        self.assertFalse(ok)
        self.assertEqual(sctp_loop._LAST_RESET_SENT_MS, 0)
