"""Z1: RC RANfunctionDescription encoder + rc-probe wire-format alignment tests.

對齊 `/home/mitlab/xapps/rc-probe/src/rc_pdu_builder.py` 的固定 hex bytes。
若 sim 這邊 decode 不出 rc-probe 送的 ControlHeader/ControlMessage，e2e 必 fail。
"""
from __future__ import annotations

from django.test import TestCase

from main.apps.e2_adapter.services.optional.codec import e2sm_rc_codec


class RcRanFunctionDescriptionTests(TestCase):
    def test_encoder_returns_aper_bytes(self) -> None:
        encoded = e2sm_rc_codec.encode_rc_ran_function_description()
        self.assertGreater(len(encoded), 30,
                           "RFD bytes too short — schema mandatory fields missing?")

    def test_rfd_round_trip(self) -> None:
        """Encode → decode 必須拿回 OID + Style 2/6 + Style 3/1。"""
        from main.apps.e2_adapter.services.optional.codec.e2ap_codec import _load_runtime
        rt = _load_runtime()
        rfd_cls = rt.E2SM_RC_IEs.E2SM_RC_RANFunctionDefinition

        encoded = e2sm_rc_codec.encode_rc_ran_function_description()
        rfd_cls.from_aper(encoded)
        decoded = rfd_cls.get_val()

        self.assertEqual(decoded["ranFunction-Name"]["ranFunction-E2SM-OID"],
                         "1.3.6.1.4.1.53148.1.1.2.3")
        self.assertEqual(decoded["ranFunction-Name"]["ranFunction-ShortName"],
                         "ORAN-E2SM-RC")

        styles = decoded["ranFunctionDefinition-Control"]["ric-ControlStyle-List"]
        style_types = sorted(s["ric-ControlStyle-Type"] for s in styles)
        self.assertEqual(style_types, [2, 3])

        # Style 2 / Action 6 with 3 RANParameters
        s2 = next(s for s in styles if s["ric-ControlStyle-Type"] == 2)
        self.assertEqual(s2["ric-ControlAction-List"][0]["ric-ControlAction-ID"], 6)
        action_params = s2["ric-ControlAction-List"][0]["ran-ControlActionParameters-List"]
        param_ids = sorted(p["ranParameter-ID"] for p in action_params)
        self.assertEqual(param_ids, [1, 2, 3])

        # Style 3 / Action 1 with 1 RANParameter (Target Cell ID)
        s3 = next(s for s in styles if s["ric-ControlStyle-Type"] == 3)
        self.assertEqual(s3["ric-ControlAction-List"][0]["ric-ControlAction-ID"], 1)


class RcProbeFixedBytesTests(TestCase):
    """Sim 必須能 decode rc-probe 預錄製的固定 hex bytes (Style 2/6 PRB quota)."""

    RC_PROBE_HEADER_HEX = "0000002a0002f859a100410102000005"
    RC_PROBE_MESSAGE_HEX = "000003000001010a00010101320002010164"

    def test_rc_probe_header_decodes_to_style_2_action_6(self) -> None:
        from main.apps.e2_adapter.services.optional.codec.e2ap_codec import _load_runtime
        rt = _load_runtime()
        ch_cls = rt.E2SM_RC_IEs.E2SM_RC_ControlHeader

        ch_cls.from_aper(bytes.fromhex(self.RC_PROBE_HEADER_HEX))
        ch_val = ch_cls.get_val()
        fmt_choice, fmt_val = ch_val["ric-controlHeader-formats"]

        self.assertEqual(fmt_choice, "controlHeader-Format1")
        self.assertEqual(int(fmt_val["ric-Style-Type"]), 2)
        self.assertEqual(int(fmt_val["ric-ControlAction-ID"]), 6)

    def test_rc_probe_message_decodes_min_max_dedicated(self) -> None:
        from main.apps.e2_adapter.services.optional.codec.e2ap_codec import _load_runtime
        rt = _load_runtime()
        cm_cls = rt.E2SM_RC_IEs.E2SM_RC_ControlMessage

        cm_cls.from_aper(bytes.fromhex(self.RC_PROBE_MESSAGE_HEX))
        cm_val = cm_cls.get_val()
        fmt_choice, fmt_val = cm_val["ric-controlMessage-formats"]

        self.assertEqual(fmt_choice, "controlMessage-Format1")
        ranp_list = fmt_val["ranP-List"]
        self.assertEqual(len(ranp_list), 3)

        params: dict[int, int] = {}
        for ranp in ranp_list:
            pid = int(ranp["ranParameter-ID"])
            value_choice = ranp["ranParameter-valueType"]
            self.assertEqual(value_choice[0], "ranP-Choice-ElementTrue")
            inner = value_choice[1]["ranParameter-value"]
            self.assertEqual(inner[0], "valueInt")
            params[pid] = int(inner[1])

        self.assertEqual(params, {1: 10, 2: 50, 3: 100})


class RicControlFailureEncoderTests(TestCase):
    def test_failure_encodes_with_cause(self) -> None:
        ric_req_id = {"requestor_id": 5, "instance_id": 7}
        cause = ("ricRequest", "ran-function-id-invalid")
        encoded = e2sm_rc_codec.encode_ric_control_failure(
            ric_req_id, ran_function_id=99, cause=cause,
        )
        self.assertGreater(len(encoded), 0)

        from main.apps.e2_adapter.services.optional.codec.e2ap_codec import _load_runtime
        rt = _load_runtime()
        pdu_cls = rt.E2AP_PDU_Descriptions.E2AP_PDU
        pdu_cls.from_aper(encoded)
        outer_choice, inner = pdu_cls.get_val()
        self.assertEqual(outer_choice, "unsuccessfulOutcome")
        self.assertEqual(inner["procedureCode"], 4)  # RICcontrol
        self.assertEqual(inner["value"][0], "RICcontrolFailure")

        ies = inner["value"][1]["protocolIEs"]
        cause_ie = next(ie for ie in ies if ie["id"] == 1)
        self.assertEqual(cause_ie["value"][1], cause)


class HandleControlReqFailureRoutingTests(TestCase):
    """Z3: 三個 negative case 在 _handle_control_req 應走 FAILURE 路徑."""

    def setUp(self) -> None:
        from main.apps.e2_adapter.services.optional.sctp_link import sctp_loop
        self.sctp_loop = sctp_loop

    def _build_request_pdu(self, ran_func_id: int, style: int, action: int,
                            param_ids: list[int]) -> bytes:
        from main.apps.e2_adapter.services.optional.codec.e2ap_codec import _load_runtime
        rt = _load_runtime()
        pdu_cls = rt.E2AP_PDU_Descriptions.E2AP_PDU
        ch_cls = rt.E2SM_RC_IEs.E2SM_RC_ControlHeader
        cm_cls = rt.E2SM_RC_IEs.E2SM_RC_ControlMessage

        ch_cls.set_val({
            "ric-controlHeader-formats": ("controlHeader-Format1", {
                "ueID": ("gNB-UEID", {
                    "amf-UE-NGAP-ID": 42,
                    "guami": {
                        "pLMNIdentity": bytes.fromhex("02f859"),
                        "aMFRegionID": (1, 8),
                        "aMFSetID": (1, 10),
                        "aMFPointer": (0, 6),
                    },
                    "gNB-CU-UE-F1AP-ID-List": [{"gNB-CU-UE-F1AP-ID": 1}],
                }),
                "ric-Style-Type": style,
                "ric-ControlAction-ID": action,
                "ric-ControlDecision": "accept",
            }),
        })
        header_bytes = ch_cls.to_aper()

        ranp_list = []
        for pid in param_ids:
            ranp_list.append({
                "ranParameter-ID": pid,
                "ranParameter-valueType": (
                    "ranP-Choice-ElementTrue",
                    {"ranParameter-value": ("valueInt", 10 * pid)},
                ),
            })
        cm_cls.set_val({
            "ric-controlMessage-formats": ("controlMessage-Format1", {
                "ranP-List": ranp_list or [{
                    "ranParameter-ID": 99,
                    "ranParameter-valueType": (
                        "ranP-Choice-ElementTrue",
                        {"ranParameter-value": ("valueInt", 0)},
                    ),
                }],
            }),
        })
        message_bytes = cm_cls.to_aper()

        pdu_cls.set_val(("initiatingMessage", {
            "procedureCode": 4,
            "criticality": "reject",
            "value": ("RICcontrolRequest", {
                "protocolIEs": [
                    {"id": 29, "criticality": "reject",
                     "value": ("RICrequestID", {"ricRequestorID": 5, "ricInstanceID": 7})},
                    {"id": 5, "criticality": "reject",
                     "value": ("RANfunctionID", ran_func_id)},
                    {"id": 22, "criticality": "reject",
                     "value": ("RICcontrolHeader", header_bytes)},
                    {"id": 23, "criticality": "reject",
                     "value": ("RICcontrolMessage", message_bytes)},
                ],
            }),
        }))
        return pdu_cls.to_aper()

    def _capture_failure_cause(self, raw_pdu: bytes) -> tuple[str, str] | None:
        from unittest.mock import patch
        sent: list[bytes] = []

        def fake_send(sock, data, ppid=70) -> bool:
            sent.append(data)
            return True

        with patch.object(self.sctp_loop, "_send_sctp", side_effect=fake_send):
            self.sctp_loop._handle_control_req(sock=None, raw_pdu=raw_pdu)

        if not sent:
            return None
        from main.apps.e2_adapter.services.optional.codec.e2ap_codec import _load_runtime
        rt = _load_runtime()
        pdu_cls = rt.E2AP_PDU_Descriptions.E2AP_PDU
        pdu_cls.from_aper(sent[-1])
        outer_choice, inner = pdu_cls.get_val()
        if outer_choice != "unsuccessfulOutcome":
            return None
        ies = inner["value"][1]["protocolIEs"]
        cause_ie = next((ie for ie in ies if ie["id"] == 1), None)
        return cause_ie["value"][1] if cause_ie else None

    def test_wrong_ran_function_id_returns_id_invalid(self) -> None:
        raw = self._build_request_pdu(ran_func_id=99, style=2, action=6,
                                        param_ids=[1, 2, 3])
        cause = self._capture_failure_cause(raw)
        self.assertEqual(cause, ("ricRequest", "ran-function-id-invalid"))

    def test_unsupported_style_action_returns_action_not_supported(self) -> None:
        raw = self._build_request_pdu(ran_func_id=3, style=99, action=99,
                                        param_ids=[1])
        cause = self._capture_failure_cause(raw)
        self.assertEqual(cause, ("ricRequest", "action-not-supported"))

    def test_missing_ran_param_returns_control_message_invalid(self) -> None:
        # Style 2/6 expects {1, 2, 3}; we send only {1, 2}
        raw = self._build_request_pdu(ran_func_id=3, style=2, action=6,
                                        param_ids=[1, 2])
        cause = self._capture_failure_cause(raw)
        self.assertEqual(cause, ("ricRequest", "control-message-invalid"))


class RcProbeES1HandoverDecodeTests(TestCase):
    """AA4 — rc-probe ES.1 (Style 3/Action 1, ranP-Choice-Structure) 必須能解, 且 sim_payload JSON-serializable.

    Reproduces 2026-05-10 04:29:58 incident: sim 收 ES.1 後 SCTP self-shutdown.
    Root cause = codec 對 ranP-Choice-Structure 留下 pycrate 物件, json.dumps 拋 TypeError,
    SCTP recv thread 沒兜底 → graceful close.
    """

    # 來自 RIC team 對拍的 ES.1 完整 E2AP RICcontrolRequest hex (77 bytes).
    ES1_PDU_HEX = (
        "00040049000005001d00050004d2000100050002000300160011100000002a0002f859"
        "401045010300000000170019180000010000440001000004"
        "0302f8590001032400000003800015000140"
    )

    def test_decode_extracts_target_cgi_plmn_and_nr_cell_id(self) -> None:
        decoded = e2sm_rc_codec.decode_ric_control_request(bytes.fromhex(self.ES1_PDU_HEX))

        self.assertEqual(decoded["style_type"], 3)
        self.assertEqual(decoded["action_id"], 1)
        self.assertEqual(decoded["ric_req_id"]["requestor_id"], 1234)
        self.assertEqual(decoded["ric_req_id"]["instance_id"], 1)
        self.assertEqual(decoded["ran_function_id"], 3)
        self.assertEqual(decoded["ueid"]["amf_ue_ngap_id"], 42)
        self.assertEqual(decoded["ueid"]["plmn_hex"], "02f859")

        # ranP[1] 應該是 Structure type, 內含 child PLMN + NRCellIdentity
        params = decoded["ran_params"]
        self.assertIn(1, params)
        self.assertEqual(params[1]["_type"], "structure")
        fields = params[1]["fields"]
        self.assertIsNotNone(fields)
        # 至少要有 PLMN (octS) + NRCellIdentity (bitS) 兩個 child
        scalar_types = []
        for child in fields.values():
            if isinstance(child, dict):
                scalar_types.append(child.get("_type"))
        self.assertIn("valueOctS", scalar_types)
        self.assertIn("valueBitS", scalar_types)

    def test_to_sim_payload_extracts_target_cgi_and_is_json_safe(self) -> None:
        import json

        decoded = e2sm_rc_codec.decode_ric_control_request(bytes.fromhex(self.ES1_PDU_HEX))
        payload = e2sm_rc_codec.to_sim_control_payload(decoded)

        self.assertIsNotNone(payload)
        self.assertEqual(payload["action"], "control_handover")
        target_cgi = payload["control_message"]["target_cgi"]
        self.assertEqual(target_cgi.get("plmn_hex"), "02f859")
        # NRCellIdentity 36-bit, rc-probe 送的值應該是非零 int (rc-probe hardcode = 56 = 0x38)
        self.assertGreater(int(target_cgi.get("nr_cell_id", 0)), 0)

        # 關鍵: 整個 payload 必須 JSON-serializable, 不可內嵌 pycrate ASN1 物件
        # (這條 assert 是 reproduce/regression 的核心 — 5/10 incident 在這炸)
        json.dumps(payload)  # 不該拋 TypeError

    def test_recv_loop_wraps_dispatch_in_try_except(self) -> None:
        """AA3 source-level guarantee — recv loop 必須包 try/except 圍住 _dispatch_pdu.

        (5/10 incident root cause: 任一 handler exception 直接讓 SCTP recv thread 死,
        socket 在 finally close → graceful SHUTDOWN. fix 把 _dispatch_pdu 包進 try/except,
        log 後繼續 listen 下一筆.)
        """
        import inspect
        from main.apps.e2_adapter.services.optional.sctp_link import sctp_loop

        src = inspect.getsource(sctp_loop._link_loop)
        # 必須要有 _dispatch_pdu 在 try block 裡 + 後面跟著 except
        self.assertIn("_dispatch_pdu(sock, pdu)", src)
        # 簡單檢查: _dispatch_pdu 之後 (在 _link_loop 同一個 source) 必須出現 except.
        idx = src.find("_dispatch_pdu(sock, pdu)")
        self.assertGreater(idx, 0)
        after = src[idx:]
        self.assertIn("except Exception", after,
                      "recv loop 必須對 _dispatch_pdu 包 except — 否則 handler bug 會殺 SCTP")
