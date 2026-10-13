"""AMF NGAP 程序:接入配號、Path Switch 後 AMF UE NGAP ID 不變、NG 換手三步、舊 gNB 的釋放不影響新關聯。"""
import json
from unittest.mock import patch

from django.test import Client, SimpleTestCase

from main.apps.amf.services.registry import amf_ue_ngap_id_for, get_registry

B = "/api/v0.1/AMF/Ngap/AmfRouter/"


def post(c, el, body):
    return c.post(B + el, json.dumps(body), content_type="application/json")


class NgapTest(SimpleTestCase):
    def setUp(self):
        get_registry().reset()
        self.c = Client()
        for gid, url in ((0xE30, "http://cu-a"), (0xE31, "http://cu-b")):
            r = post(self.c, "ng_setup", {"gnb_id": gid, "gnb_name": f"g{gid:x}", "cu_url": url, "plmn": "20895", "tac": 1})
            self.assertEqual(r.status_code, 200, r.content)

    def _attach(self, ue="p00", gnb=0xE30, ran=11):
        with patch("main.apps.amf.services.ngap_procedures._cu_post") as cu:
            r = post(self.c, "initial_ue_message", {"gnb_id": gnb, "ran_ue_ngap_id": ran, "ue_id": ue, "cell_id": "e30:a"})
        return r, cu

    def test_initial_ue_message_assigns_legacy_compatible_id(self):
        r, _ = self._attach()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["data"]["amf_ue_ngap_id"], amf_ue_ngap_id_for("p00"))
        self.assertEqual(get_registry().ue_by_ran(0xE30, 11).ue_id, "p00")

    def test_unknown_gnb_rejected(self):
        with patch("main.apps.amf.services.ngap_procedures._cu_post"):
            r = post(self.c, "initial_ue_message", {"gnb_id": 0xE3F, "ran_ue_ngap_id": 1, "ue_id": "x"})
        self.assertEqual(r.status_code, 409)

    def test_path_switch_keeps_amf_id_changes_ran_id(self):
        self._attach()
        amf = amf_ue_ngap_id_for("p00")
        r = post(self.c, "path_switch_request", {"gnb_id": 0xE31, "ran_ue_ngap_id": 77, "amf_ue_ngap_id": amf, "cell_id": "e31:b"})
        self.assertEqual(r.status_code, 200, r.content)
        ue = get_registry().ue(amf)
        self.assertEqual((ue.gnb_id, ue.ran_ue_ngap_id, ue.cell_id), (0xE31, 77, "e31:b"))
        self.assertIsNone(get_registry().ue_by_ran(0xE30, 11))
        # 舊 gNB 事後送的釋放不影響新關聯
        post(self.c, "ue_context_release", {"amf_ue_ngap_id": amf, "gnb_id": 0xE30})
        self.assertEqual(get_registry().ue(amf).cm_state, "CONNECTED")

    def test_ng_handover_three_steps(self):
        self._attach()
        amf = amf_ue_ngap_id_for("p00")
        with patch("main.apps.amf.services.ngap_procedures._cu_post", return_value={"data": {"ran_ue_ngap_id": 99}}) as cu:
            r = post(self.c, "handover_required", {"gnb_id": 0xE30, "ran_ue_ngap_id": 11, "amf_ue_ngap_id": amf,
                                                   "target_gnb_id": 0xE31, "target_cell_id": "e31:b"})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(cu.call_args[0][0], "http://cu-b")
        self.assertEqual(r.json()["data"]["target_ran_ue_ngap_id"], 99)
        post(self.c, "handover_notify", {"gnb_id": 0xE31, "ran_ue_ngap_id": 99, "amf_ue_ngap_id": amf, "cell_id": "e31:b"})
        self.assertEqual(get_registry().ue(amf).gnb_id, 0xE31)

    def test_handover_required_from_wrong_gnb(self):
        self._attach()
        r = post(self.c, "handover_required", {"gnb_id": 0xE31, "amf_ue_ngap_id": amf_ue_ngap_id_for("p00"),
                                               "target_gnb_id": 0xE30, "target_cell_id": "e30:a"})
        self.assertEqual(r.status_code, 404)
