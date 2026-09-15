"""Ue create API 行為(backend_rule §3-4)。"""
from django.test import Client, TestCase

BASE = "/api/v0.1/Scene_management_backend/Equipment_ue"


class UeCreateApiTest(TestCase):
    def test_post_only(self):
        self.assertEqual(Client().get(f"{BASE}/UeController/create").status_code, 405)

    def test_rejects_bad_json(self):
        r = Client().post(f"{BASE}/UeController/create", data="{not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)
