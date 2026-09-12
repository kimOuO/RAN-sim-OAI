"""Scene update API 行為(backend_rule §3-4)。"""
from django.test import Client, TestCase

BASE = "/api/v0.1/Network_element_registry/Scene_layout"


class SceneUpdateApiTest(TestCase):
    def test_post_only(self):
        self.assertEqual(Client().get(f"{BASE}/SceneController/update").status_code, 405)

    def test_rejects_bad_json(self):
        r = Client().post(f"{BASE}/SceneController/update", data="{not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)
