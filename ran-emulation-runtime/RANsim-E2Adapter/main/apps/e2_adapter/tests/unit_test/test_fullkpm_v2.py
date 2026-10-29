"""E2SM-DTFULLKPM v2(func 7):OID 不在 O-RAN 企業號下、每則 indication 自足且不超過上限。"""
from __future__ import annotations

import json
import random
import zlib

from django.test import TestCase

from main.apps.e2_adapter.services.optional.codec import e2sm_fullkpm_codec as fk


def _sample(n_gnb=2, cells_per_gnb=3, ues_per_cell=4, unattached=2, pm_cols=190, seed=0):
    rnd = random.Random(seed)
    e2, ue_status, pm, bbu = [], [], {}, {"timestamp": "20261016.1500+0000"}
    for g in range(n_gnb):
        gnb = f"gnb{g}"
        cells = []
        for c in range(cells_per_gnb):
            pci = g * 10 + c
            cid = f"{g:06x}{c:09x}"
            cells.append({"cell_id": cid, "ran_name": gnb, "pci": pci,
                          "ues": [{"ue_id": f"u{g}{c}{k}", "rsrp": -80 - k} for k in range(ues_per_cell)], "beams": []})
            for k in range(ues_per_cell):
                ue_status.append({"ue_id": f"u{g}{c}{k}", "serving_gnb": gnb, "serving_pci": pci,
                                  "all_rsrp": {gnb: -80.0 - k}, "noise": rnd.random()})
            pm.setdefault(f"gnb-{gnb}", []).append({"cell_id": cid, **{f"cu_C{i}": str(rnd.randint(0, 10**6)) for i in range(pm_cols)}})
        e2.append({"gnb_id": gnb, "timestamp": 1, "cells": cells})
        bbu[f"gnb-{gnb}"] = {"cpu": 10.0 + g, "mem": 30.0}
    for k in range(unattached):
        ue_status.append({"ue_id": f"idle{k}", "serving_gnb": None, "serving_pci": None})
    return {"timestamp_ms": 1792161665613, "scene_sim_ms": 5000, "compute_ms": 17, "tick_ms": 500,
            "e2": e2, "ue_status": ue_status, "pm": pm, "bbu_status": bbu, "warnings": ["w1"]}


def _decode(payloads):
    return [(json.loads(h), json.loads(zlib.decompress(m))) for h, m in payloads]


class FullKpmV2Tests(TestCase):
    def test_oid_not_under_oran_enterprise_number(self) -> None:
        self.assertFalse(fk.FULLKPM_V2_OID.startswith("1.3.6.1.4.1.53148"))
        self.assertTrue(fk.FULLKPM_V2_OID.startswith("2.25."))
        rfd = json.loads(fk.encode_fullkpm_v2_ran_function_description())
        self.assertEqual(rfd["ranFunctionName"]["ranFunctionServiceModelOID"], fk.FULLKPM_V2_OID)

    def test_one_self_contained_report_per_cell_plus_node(self) -> None:
        data = _sample()
        out = _decode(fk.build_indication_payloads_v2(data, sn=9))
        cells = [(h, b) for h, b in out if h["report"] == "cell"]
        self.assertEqual(len(cells), 6)
        self.assertEqual(sum(h["report"] == "node" for h, _ in out), 1)
        for i, (h, b) in enumerate(out):
            self.assertEqual((h["format"], h["sn"], h["report_index"], h["report_count"]), ("DTFULLKPM-v2", 9, i, len(out)))
            self.assertEqual(b["timestamp_ms"], data["timestamp_ms"])
        for h, b in cells:
            self.assertEqual(b["cell"]["cell_id"], h["cell_id"])
            self.assertEqual(len(b["pm"]), 1)
            self.assertEqual(b["pm"][0]["cell_id"], h["cell_id"])
            self.assertTrue(all(u["serving_pci"] == b["cell"]["pci"] for u in b["ue_status"]))
            self.assertEqual(b["bbu_status"]["cpu"], data["bbu_status"][f"gnb-{h['gnb_id']}"]["cpu"])
        node = next(b for h, b in out if h["report"] == "node")
        self.assertEqual([u["ue_id"] for u in node["ue_status"]], ["idle0", "idle1"])
        self.assertEqual(node["warnings"], ["w1"])

    def test_no_ue_lost_or_duplicated(self) -> None:
        data = _sample()
        out = _decode(fk.build_indication_payloads_v2(data, sn=1))
        got = sorted(u["ue_id"] for _, b in out for u in b["ue_status"])
        self.assertEqual(got, sorted(u["ue_id"] for u in data["ue_status"]))

    def test_large_cell_is_paged_and_every_message_under_limit(self) -> None:
        data = _sample(n_gnb=1, cells_per_gnb=1, ues_per_cell=400)
        limit = 3000
        payloads = fk.build_indication_payloads_v2(data, sn=2, limit=limit)
        self.assertGreater(len(payloads), 2)
        self.assertTrue(all(len(m) <= limit for _, m in payloads))
        out = _decode(payloads)
        pages = [(h, b) for h, b in out if h["report"] == "cell"]
        self.assertEqual([h["ue_page"] for h, _ in pages], list(range(len(pages))))
        self.assertTrue(all(h["ue_pages"] == len(pages) for h, _ in pages))
        self.assertIn("pm", pages[0][1])
        self.assertTrue(all(b["cell"]["cell_id"] == pages[0][0]["cell_id"] for _, b in pages))
        self.assertEqual(sum(len(b["cell"]["ues"]) for _, b in pages), 400)
        self.assertEqual(sum(len(b["ue_status"]) for _, b in pages), 400)

    def test_v1_unchanged(self) -> None:
        self.assertEqual(fk.FULLKPM_RAN_FUNCTION_ID, 5)
        self.assertEqual(fk.FULLKPM_OID, "1.3.6.1.4.1.53148.1.1.2.100")
        hdr, _ = fk.build_indication_payloads(_sample(), sn=3)[0]
        self.assertEqual(json.loads(hdr)["format"], "DTFULLKPM-v1")
