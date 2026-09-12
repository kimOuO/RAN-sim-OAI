from django.test import Client, TestCase

BASE = "/api/v0.1/Building_geometry_ingest/Scan_mesh_ingest"


class ReadApiTest(TestCase):
    def test_post_only(self):
        self.assertEqual(Client().get(f"{BASE}/ScanAssetReader/read").status_code, 405)

    def test_empty_list(self):
        r = Client().post(f"{BASE}/ScanAssetReader/read", data="{}", content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"], [])
