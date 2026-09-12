"""LaunchRequest delete API 行為(backend_rule §3-4)。"""
from django.test import Client, TestCase

BASE = "/api/v0.1/Run_orchestrator/Run_lifecycle"


class LaunchRequestDeleteApiTest(TestCase):
    def test_post_only(self):
        self.assertEqual(Client().get(f"{BASE}/LaunchRequestController/delete").status_code, 405)

    def test_rejects_bad_json(self):
        r = Client().post(f"{BASE}/LaunchRequestController/delete", data="{not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)
