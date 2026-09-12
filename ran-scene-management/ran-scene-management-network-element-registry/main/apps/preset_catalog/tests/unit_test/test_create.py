"""Material create API 行為(backend_rule §3-4)。"""
from django.test import Client, TestCase

BASE = "/api/v0.1/Network_element_registry/Preset_catalog"


class MaterialCreateApiTest(TestCase):
    def test_post_only(self):
        self.assertEqual(Client().get(f"{BASE}/MaterialController/create").status_code, 405)

    def test_rejects_bad_json(self):
        r = Client().post(f"{BASE}/MaterialController/create", data="{not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)
