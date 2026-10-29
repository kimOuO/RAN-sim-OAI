"""KPM RANfunction-Description 宣告與實際送出格式一致 + ActionDefinition 各 Format 解碼。

實際送出的 IndicationMessage 是 Format 3(per-UE),v2.0.03 規定對應 Report Style 4/5;
Style 1 為相容既有 xApp 保留。
"""
from __future__ import annotations

from django.test import TestCase

from main.apps.e2_adapter.services.optional.codec import e2sm_kpm_codec
from main.apps.e2_adapter.services.optional.codec.e2_subscription_codec import _decode_action_metrics
from main.apps.e2_adapter.services.optional.codec.e2ap_codec import _load_runtime

_METRICS = ["DRB.UEThpDl", "RSRP"]
_UE_ID = ("gNB-UEID", {
    "amf-UE-NGAP-ID": 1,
    "guami": {"pLMNIdentity": b"\x00\xf1\x10", "aMFRegionID": (1, 8),
              "aMFSetID": (1, 10), "aMFPointer": (1, 6)},
})


def _subscript_info() -> dict:
    return {
        "measInfoList": [{"measType": ("measName", m),
                          "labelInfoList": [{"measLabel": {"noLabel": "true"}}]} for m in _METRICS],
        "granulPeriod": 1000,
    }


def _encode_action(style: int, fmt: str, body: dict) -> bytes:
    ad_cls = _load_runtime().E2SM_KPM_IEs.E2SM_KPM_ActionDefinition
    ad_cls.set_val({"ric-Style-Type": style, "actionDefinition-formats": (fmt, body)})
    return ad_cls.to_aper()


class KpmRanFunctionDescriptionTests(TestCase):
    def _report_styles(self) -> dict[int, dict]:
        rfd_cls = _load_runtime().E2SM_KPM_IEs.E2SM_KPM_RANfunction_Description
        rfd_cls.from_aper(e2sm_kpm_codec.encode_kpm_ran_function_description())
        return {s["ric-ReportStyle-Type"]: s for s in rfd_cls.get_val()["ric-ReportStyle-List"]}

    def test_advertises_ue_level_style_matching_indication_format3(self) -> None:
        styles = self._report_styles()
        self.assertIn(4, styles)
        self.assertEqual(styles[4]["ric-ActionFormat-Type"], 4)
        self.assertEqual(styles[4]["ric-IndicationMessageFormat-Type"], 3)

    def test_keeps_style1_for_existing_xapps(self) -> None:
        styles = self._report_styles()
        self.assertEqual(list(styles)[0], 1)
        self.assertEqual(styles[1]["ric-ActionFormat-Type"], 1)

    def test_sent_indication_is_format3(self) -> None:
        msg = e2sm_kpm_codec.encode_kpm_indication_message({"ue_meas_report_lst": [
            {"ue_id": "ue1", "amf_ue_ngap_id": 1, "meas_data_lst": [{"name": "DRB.UEThpDl", "value": 1}]}]})
        fmt, _ = e2sm_kpm_codec.decode_kpm_indication_message(msg)["indicationMessage-formats"]
        self.assertEqual(fmt, "indicationMessage-Format3")


class ActionDefinitionDecodeTests(TestCase):
    def test_format1(self) -> None:
        data = _encode_action(1, "actionDefinition-Format1", _subscript_info())
        self.assertEqual(_decode_action_metrics(data), _METRICS)

    def test_format2(self) -> None:
        data = _encode_action(2, "actionDefinition-Format2", {"ueID": _UE_ID, "subscriptInfo": _subscript_info()})
        self.assertEqual(_decode_action_metrics(data), _METRICS)

    def test_format4(self) -> None:
        cond = [{"testCondInfo": {"testType": ("rSRP", "true")}}]
        data = _encode_action(4, "actionDefinition-Format4",
                              {"matchingUeCondList": cond, "subscriptionInfo": _subscript_info()})
        self.assertEqual(_decode_action_metrics(data), _METRICS)

    def test_format5(self) -> None:
        ues = [{"ueID": _UE_ID}, {"ueID": _UE_ID}]
        data = _encode_action(5, "actionDefinition-Format5",
                              {"matchingUEidList": ues, "subscriptionInfo": _subscript_info()})
        self.assertEqual(_decode_action_metrics(data), _METRICS)
