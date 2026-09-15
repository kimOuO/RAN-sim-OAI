from django.test import Client, TestCase

BASE = "/api/v0.1/Scene_management_backend/Render_osm_footprint"


class ReadApiTest(TestCase):
    def test_post_only(self):
        self.assertEqual(Client().get(f"{BASE}/OsmMapAssetReader/read").status_code, 405)

    def test_empty_list(self):
        r = Client().post(f"{BASE}/OsmMapAssetReader/read", data="{}", content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"], [])
