"""多 gNB(2026-09-27):gNB 的 e2_index 自動配發、唯一、上限 16;場景 e2_block 範圍 1–15。"""
import json

from django.test import Client, TestCase

_GNB = "/api/v0.1/Scene_management_backend/Equipment_ran/GnbController/create"
_SCENE = "/api/v0.1/Scene_management_backend/Field_scene/SceneController/create"
_SCENE_UPD = "/api/v0.1/Scene_management_backend/Field_scene/SceneController/update"


class GnbE2IndexTest(TestCase):
    def setUp(self):
        self.c = Client()
        r = self.c.post(_SCENE, json.dumps({"name": "t"}), content_type="application/json")
        self.assertEqual(r.status_code, 201, r.content)
        self.scene = r.json()["data"]["scene_uuid"]

    def _gnb(self, name, **extra):
        return self.c.post(_GNB, json.dumps({"name": name, "f_scene_uuid": self.scene, **extra}),
                           content_type="application/json")

    def test_auto_assigns_smallest_free_index(self):
        idx = [self._gnb(f"g{i}").json()["data"]["e2_index"] for i in range(3)]
        self.assertEqual(idx, [0, 1, 2])

    def test_explicit_index_and_duplicate_rejected(self):
        self.assertEqual(self._gnb("a", e2_index=5).json()["data"]["e2_index"], 5)
        r = self._gnb("b", e2_index=5)
        self.assertEqual(r.status_code, 400)
        # 自動配發會跳過已用的 5
        self.assertEqual(self._gnb("c").json()["data"]["e2_index"], 0)

    def test_limit_16_per_scene(self):
        for i in range(16):
            self.assertEqual(self._gnb(f"g{i}").status_code, 201)
        r = self._gnb("g16")
        self.assertEqual(r.status_code, 400)
        self.assertIn("e2_index", r.json()["errors"] if "errors" in r.json() else r.content.decode())

    def test_out_of_range_index_rejected(self):
        self.assertEqual(self._gnb("x", e2_index=16).status_code, 400)

    def test_scene_e2_block_range(self):
        ok = self.c.post(_SCENE_UPD, json.dumps({"scene_uuid": self.scene, "e2_block": 15}), content_type="application/json")
        self.assertEqual(ok.status_code, 200, ok.content)
        for bad in (0, 16):
            r = self.c.post(_SCENE_UPD, json.dumps({"scene_uuid": self.scene, "e2_block": bad}), content_type="application/json")
            self.assertEqual(r.status_code, 400, (bad, r.content))


_DU = "/api/v0.1/Scene_management_backend/Equipment_ran/DuController/create"
_CELL = "/api/v0.1/Scene_management_backend/Equipment_ran/CellController/create"


class CellLocalIdTest(TestCase):
    """local_cell_id 在同一個 gNB 內(跨它所有 DU)唯一,不同 gNB 各自從 0 起算。"""

    def setUp(self):
        self.c = Client()
        scene = self.c.post(_SCENE, json.dumps({"name": "t"}), content_type="application/json").json()["data"]["scene_uuid"]
        self.g = [self.c.post(_GNB, json.dumps({"name": f"g{i}", "f_scene_uuid": scene}), content_type="application/json").json()["data"]["gnb_uuid"] for i in range(2)]

    def _du(self, gnb):
        r = self.c.post(_DU, json.dumps({"name": "d", "f_gnb_uuid": gnb}), content_type="application/json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()["data"]["du_uuid"]

    def _cell(self, du, **extra):
        return self.c.post(_CELL, json.dumps({"name": "c", "f_du_uuid": du, **extra}), content_type="application/json")

    def test_unique_across_dus_of_same_gnb(self):
        d0, d1 = self._du(self.g[0]), self._du(self.g[0])
        ids = [self._cell(d0).json()["data"]["local_cell_id"], self._cell(d1).json()["data"]["local_cell_id"],
               self._cell(d0).json()["data"]["local_cell_id"]]
        self.assertEqual(ids, [0, 1, 2])

    def test_independent_per_gnb(self):
        a, b = self._du(self.g[0]), self._du(self.g[1])
        self.assertEqual(self._cell(a).json()["data"]["local_cell_id"], 0)
        self.assertEqual(self._cell(b).json()["data"]["local_cell_id"], 0)

    def test_duplicate_rejected(self):
        d = self._du(self.g[0])
        self.assertEqual(self._cell(d, local_cell_id=7).status_code, 201)
        self.assertEqual(self._cell(d, local_cell_id=7).status_code, 400)
