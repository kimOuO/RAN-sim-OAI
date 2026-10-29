"""run knob → E2 adapter env:只進 e2adapter 實例,不帶時不改變任何實例。"""
from __future__ import annotations

from django.test import SimpleTestCase

from main.apps.run_lifecycle.services.optional import container_spawner
from ran_sim_protocol.run_topology import build_from_tree

RUN = "scene_run-00000000000000000000000000abcd1234"
TREE = {"gnbs": [
    {"name": "src", "e2_index": 0, "dus": [{"name": "a", "gnb_du_id": 1, "cells": [{"name": "s0", "pci": 1, "local_cell_id": 0}]}]},
    {"name": "nbr", "e2_index": 1, "dus": [{"name": "b", "gnb_du_id": 1, "cells": [{"name": "n0", "pci": 2, "local_cell_id": 0}]}]},
]}


class PlanE2EnvTests(SimpleTestCase):
    def setUp(self) -> None:
        self.topo = build_from_tree(TREE, run_uuid=RUN, block=3)

    def test_e2_env_only_on_e2adapters(self) -> None:
        plan = container_spawner.plan_instances(RUN, self.topo, e2_env={"E2SM_FULLKPM2_ENABLE": "on"})
        e2 = [it for it in plan if it["role"] == "e2adapter"]
        self.assertEqual(len(e2), 2)
        self.assertTrue(all(it["env"]["E2SM_FULLKPM2_ENABLE"] == "on" for it in e2))
        self.assertTrue(all("E2SM_FULLKPM2_ENABLE" not in it["env"] for it in plan if it["role"] != "e2adapter"))

    def test_default_unchanged(self) -> None:
        plan = container_spawner.plan_instances(RUN, self.topo)
        self.assertTrue(all("E2SM_FULLKPM2_ENABLE" not in it["env"] for it in plan))
        self.assertEqual({it["env"]["GNB_NAME"] for it in plan if it["role"] == "e2adapter"}, {"src", "nbr"})

    def test_no_ric_has_no_e2adapter(self) -> None:
        plan = container_spawner.plan_instances(RUN, self.topo, no_ric=True, e2_env={"E2SM_FULLKPM2_ENABLE": "on"})
        self.assertFalse([it for it in plan if it["role"] == "e2adapter"])
