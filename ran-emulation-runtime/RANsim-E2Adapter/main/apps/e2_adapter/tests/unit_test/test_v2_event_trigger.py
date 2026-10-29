"""v2 自訂 E2SM(func 7 / 8)的事件觸發:自有 JSON 格式、不合規回 RICsubscriptionFailure、遷移期接受舊 KPM 格式。"""
from __future__ import annotations

import json

from django.test import TestCase

from main.apps.e2_adapter.services.optional.codec import e2_subscription_codec as sub
from main.apps.e2_adapter.services.optional.codec import e2sm_anr_codec as anr
from main.apps.e2_adapter.services.optional.codec import e2sm_fullkpm_codec as fk
from main.apps.e2_adapter.services.optional.codec.e2ap_codec import _load_runtime


def _legacy_kpm_trigger(period_ms: int) -> bytes:
    et = _load_runtime().E2SM_KPM_IEs.E2SM_KPM_EventTriggerDefinition
    et.set_val({"eventDefinition-formats": ("eventDefinition-Format1", {"reportingPeriod": period_ms})})
    return et.to_aper()


class V2EventTriggerTests(TestCase):
    def test_json_trigger_roundtrip(self) -> None:
        self.assertEqual(fk.decode_v2_event_trigger(fk.encode_v2_event_trigger(1000)), (1000, False))
        self.assertEqual(fk.decode_v2_event_trigger(b'{"eventTriggerFormat":1,"reportingPeriodMs":500}'), (500, False))

    def test_invalid_json_rejected_with_semantic_error(self) -> None:
        for raw in (b'{"eventTriggerFormat":2,"reportingPeriodMs":1000}', b'{"eventTriggerFormat":1,"reportingPeriodMs":50}',
                    b'{"eventTriggerFormat":1,"reportingPeriodMs":"1000"}', b'{"eventTriggerFormat":1}'):
            with self.assertRaises(fk.EventTriggerError) as cm:
                fk.decode_v2_event_trigger(raw)
            self.assertEqual(cm.exception.cause, ("protocol", "semantic-error"), raw)

    def test_garbage_and_empty_rejected(self) -> None:
        for raw in (b"", b"\xff\x00\x13", b"[1,2]"):
            with self.assertRaises(fk.EventTriggerError) as cm:
                fk.decode_v2_event_trigger(raw, allow_legacy=True)
            self.assertEqual(cm.exception.cause, ("protocol", "abstract-syntax-error-falsely-constructed-message"), raw)

    def test_legacy_kpm_only_when_allowed(self) -> None:
        raw = _legacy_kpm_trigger(1000)
        self.assertEqual(fk.decode_v2_event_trigger(raw, allow_legacy=True), (1000, True))
        with self.assertRaises(fk.EventTriggerError):
            fk.decode_v2_event_trigger(raw, allow_legacy=False)

    def test_subscription_failure_pdu(self) -> None:
        pdu = sub.encode_ric_subscription_failure({"requestor_id": 123, "instance_id": 7}, 8, ("protocol", "semantic-error"))
        cls = _load_runtime().E2AP_PDU_Descriptions.E2AP_PDU
        cls.from_aper(pdu)
        kind, body = cls.get_val()
        self.assertEqual((kind, body["procedureCode"], body["value"][0]), ("unsuccessfulOutcome", 8, "RICsubscriptionFailure"))
        ies = {ie["id"]: ie["value"][1] for ie in body["value"][1]["protocolIEs"]}
        self.assertEqual(ies[29], {"ricRequestorID": 123, "ricInstanceID": 7})
        self.assertEqual(ies[5], 8)
        self.assertEqual(ies[1], ("protocol", "semantic-error"))

    def test_rfds_declare_own_trigger_style(self) -> None:
        for raw in (fk.encode_fullkpm_v2_ran_function_description(), anr.encode_anr_v2_ran_function_description()):
            rfd = json.loads(raw)
            self.assertEqual([s["ricEventTriggerStyleType"] for s in rfd["listOfSupportedEventTriggerStyles"]], [1])
            self.assertTrue(all(s["ricEventTriggerStyleType"] == 1 for s in rfd["listOfSupportedReportStyles"]))
            self.assertNotIn("E2SM-KPM", raw.decode())
