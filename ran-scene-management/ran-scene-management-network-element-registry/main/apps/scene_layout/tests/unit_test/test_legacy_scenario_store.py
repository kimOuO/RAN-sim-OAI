
"""相容端點:匯入後以舊路徑 read 回來,raw_json 語意等於原檔。"""
import json
from pathlib import Path

from django.test import Client, TestCase

from main.apps.scene_layout.services.optional.scenario_import.roundtrip import canonical
from main.apps.scene_layout.services.optional.scenario_import.scenario_v1 import import_scenario

FIXTURE = Path(__file__).resolve().parents[7] / "docs" / "scenarios" / "cco_20min.json"


class LegacyScenarioStoreTest(TestCase):
    def test_read_matches_original(self):
        raw = json.loads(FIXTURE.read_text())
        import_scenario(raw)
        r = Client().post("/api/v0.1/RAN/Scenario/ScenarioController/read", data=json.dumps({"scenario_id": "cco_20min"}), content_type="application/json")
        self.assertEqual(r.status_code, 200)
        d = r.json()["data"]
        self.assertEqual(d["precompute_status"], "pending")
        self.assertEqual(canonical(d["raw_json"]), canonical(raw))
        lst = Client().post("/api/v0.1/RAN/Scenario/ScenarioController/list", data="{}", content_type="application/json").json()["data"]
        self.assertEqual([x["scenario_id"] for x in lst], ["cco_20min"])
