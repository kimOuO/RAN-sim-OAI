"""RC Style 2 / Action 8(天線 / 波束控制,2026-09-17)。

- RAN Function Description 宣告 action 8
- ControlMessage 的 4 個 ranP 解成 sim payload(target_cgi / tilt / beams / max_layers)
- sim CU 拒絕 → RICcontrolFailure(以前一律 ACK)
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from main.apps.e2_adapter.services.optional.codec import e2sm_rc_codec
from main.apps.e2_adapter.services.optional.codec.e2ap_codec import _load_runtime

NCI_E01_NBR = 0xB2A9CD944   # e01:nbr 的 NR Cell ID(CU 的 SHA-1 對映)


def _elem(pid, kind, val):
    return {"ranParameter-ID": pid,
            "ranParameter-valueType": ("ranP-Choice-ElementTrue", {"ranParameter-value": (kind, val)})}


def build_beam_pdu(*, tilt=None, beams=None, layers=None, with_cell=True, ran_func_id=3) -> bytes:
    rt = _load_runtime()
    ch = rt.E2SM_RC_IEs.E2SM_RC_ControlHeader
    cm = rt.E2SM_RC_IEs.E2SM_RC_ControlMessage
    pdu = rt.E2AP_PDU_Descriptions.E2AP_PDU
    ch.set_val({"ric-controlHeader-formats": ("controlHeader-Format1", {
        "ueID": ("gNB-UEID", {
            "amf-UE-NGAP-ID": 0,
            "guami": {"pLMNIdentity": bytes.fromhex("02f859"), "aMFRegionID": (1, 8),
                      "aMFSetID": (1, 10), "aMFPointer": (0, 6)},
        }),
        "ric-Style-Type": 2, "ric-ControlAction-ID": 8, "ric-ControlDecision": "accept",
    })})
    ranp = []
    if with_cell:
        ranp.append({"ranParameter-ID": 1, "ranParameter-valueType": ("ranP-Choice-Structure", {
            "ranParameter-Structure": {"sequence-of-ranParameters": [
                _elem(1, "valueOctS", bytes.fromhex("02f859")),
                _elem(2, "valueBitS", (NCI_E01_NBR, 36)),
            ]}})})
    if tilt is not None:
        ranp.append(_elem(2, "valueInt", tilt))
    if beams is not None:
        ranp.append(_elem(3, "valuePrintableString", beams))
    if layers is not None:
        ranp.append(_elem(4, "valueInt", layers))
    cm.set_val({"ric-controlMessage-formats": ("controlMessage-Format1", {"ranP-List": ranp})})
    pdu.set_val(("initiatingMessage", {
        "procedureCode": 4, "criticality": "reject",
        "value": ("RICcontrolRequest", {"protocolIEs": [
            {"id": 29, "criticality": "reject", "value": ("RICrequestID", {"ricRequestorID": 5, "ricInstanceID": 9})},
            {"id": 5, "criticality": "reject", "value": ("RANfunctionID", ran_func_id)},
            {"id": 22, "criticality": "reject", "value": ("RICcontrolHeader", ch.to_aper())},
            {"id": 23, "criticality": "reject", "value": ("RICcontrolMessage", cm.to_aper())},
        ]}),
    }))
    return pdu.to_aper()


class BeamControlAdvertisementTests(TestCase):
    def test_rfd_declares_style2_action8(self):
        rfd = e2sm_rc_codec._rc_ies().E2SM_RC_RANFunctionDefinition
        rfd.from_aper(e2sm_rc_codec.encode_rc_ran_function_description())
        styles = rfd.get_val()["ranFunctionDefinition-Control"]["ric-ControlStyle-List"]
        s2 = next(s for s in styles if s["ric-ControlStyle-Type"] == 2)
        acts = {a["ric-ControlAction-ID"]: a for a in s2["ric-ControlAction-List"]}
        self.assertIn(6, acts)
        self.assertIn(8, acts)
        self.assertEqual([p["ranParameter-ID"] for p in acts[8]["ran-ControlActionParameters-List"]], [1, 2, 3, 4])


class BeamControlDecodeTests(TestCase):
    def test_all_params(self):
        d = e2sm_rc_codec.decode_ric_control_request(build_beam_pdu(tilt=65, beams="0, 3,5", layers=2))
        self.assertEqual((d["style_type"], d["action_id"]), (2, 8))
        p = e2sm_rc_codec.to_sim_control_payload(d)
        self.assertEqual(p["control_header"]["control_style"], 2)
        self.assertEqual(p["control_header"]["control_action_id"], 8)
        m = p["control_message"]
        self.assertEqual(m["target_cgi"], {"plmn_hex": "02f859", "nr_cell_id": NCI_E01_NBR})
        self.assertAlmostEqual(m["electrical_tilt_deg"], 6.5)
        self.assertEqual(m["active_beam_ids"], [0, 3, 5])
        self.assertEqual(m["max_layers"], 2)

    def test_only_layers_leaves_others_absent(self):
        m = e2sm_rc_codec.to_sim_control_payload(
            e2sm_rc_codec.decode_ric_control_request(build_beam_pdu(layers=1)))["control_message"]
        self.assertEqual(m["max_layers"], 1)
        self.assertNotIn("electrical_tilt_deg", m)
        self.assertNotIn("active_beam_ids", m)

    def test_empty_beam_string_means_reset(self):
        m = e2sm_rc_codec.to_sim_control_payload(
            e2sm_rc_codec.decode_ric_control_request(build_beam_pdu(beams="")))["control_message"]
        self.assertEqual(m["active_beam_ids"], [])


class BeamControlOutcomeTests(TestCase):
    def setUp(self):
        from main.apps.e2_adapter.services.optional.sctp_link import sctp_loop
        self.sctp_loop = sctp_loop

    def _run(self, raw, sim_result):
        sent = []
        with patch.object(self.sctp_loop, "_send_sctp", side_effect=lambda s, d, ppid=70: sent.append(d) or True), \
             patch("main.apps.e2_adapter.services.optional.sim_bridge.sim_http_client.call_control_request",
                   return_value=sim_result) as call:
            self.sctp_loop._handle_control_req(sock=None, raw_pdu=raw)
        rt = _load_runtime()
        pdu = rt.E2AP_PDU_Descriptions.E2AP_PDU
        pdu.from_aper(sent[-1])
        return pdu.get_val()[0], call

    def test_sim_ok_sends_ack_and_forwards(self):
        outcome, call = self._run(build_beam_pdu(tilt=20), {"cell_id": "e01:nbr"})
        self.assertEqual(outcome, "successfulOutcome")
        self.assertAlmostEqual(call.call_args[0][0]["control_message"]["electrical_tilt_deg"], 2.0)

    def test_sim_rejects_sends_failure(self):
        outcome, _ = self._run(build_beam_pdu(tilt=20), None)
        self.assertEqual(outcome, "unsuccessfulOutcome")

    def test_missing_cell_is_invalid(self):
        outcome, call = self._run(build_beam_pdu(tilt=20, with_cell=False), {"x": 1})
        self.assertEqual(outcome, "unsuccessfulOutcome")
        call.assert_not_called()
