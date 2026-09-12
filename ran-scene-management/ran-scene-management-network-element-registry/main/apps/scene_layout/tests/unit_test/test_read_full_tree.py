
"""匯入一份劇本後 read_full_tree 的形狀與計數。"""
import json
from pathlib import Path

from django.test import Client, TestCase

from main.apps.scene_layout.services.optional.scenario_import.scenario_v1 import import_scenario

BASE = "/api/v0.1/Network_element_registry/Scene_layout"
FIXTURE = Path(__file__).resolve().parents[7] / "docs" / "scenarios" / "cco_20min.json"


class ReadFullTreeTest(TestCase):
    def test_tree_counts_and_nesting(self):
        raw = json.loads(FIXTURE.read_text())
        r = import_scenario(raw)
        resp = Client().post(f"{BASE}/SceneReader/read_full_tree", data=json.dumps({"scene_run_uuid": r["scene_run_uuid"]}),
                             content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        t = resp.json()["data"]
        self.assertEqual(len(t["gnbs"]), 1)
        self.assertEqual(len(t["gnbs"][0]["dus"]), 1)
        cells = t["gnbs"][0]["dus"][0]["cells"]
        self.assertEqual(len(cells), 2)
        self.assertIsNotNone(cells[0]["ru"])
        self.assertEqual(cells[0]["ru"]["antenna_preset"]["pattern"], "iso")
        self.assertEqual(len(t["ues"]), 1)
        self.assertGreater(len(t["ues"][0]["waypoints"]), 0)
        self.assertEqual(len(t["ues"][0]["traffic"]), 1)
        self.assertEqual(t["run"]["knobs"]["default_serving_cell"], "gnbDT_c0")
        self.assertEqual(t["run"]["knobs"]["cell_quotas"][0]["max_prb"], 10)
        self.assertEqual(t["run"]["sim_dt_ms"], 500)

    def test_requires_identifier(self):
        resp = Client().post(f"{BASE}/SceneReader/read_full_tree", data="{}", content_type="application/json")
        self.assertEqual(resp.status_code, 400)
