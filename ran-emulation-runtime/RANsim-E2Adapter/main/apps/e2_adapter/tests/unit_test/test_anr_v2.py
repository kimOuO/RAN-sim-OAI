"""E2SM-ANR v2(func 8):OID 不在 O-RAN 企業號下;每則 indication 自足、不超過上限、條目不遺失;
關係變更依 source cell 各送一則。"""
from __future__ import annotations

import json
import random
import zlib

from django.test import TestCase

from main.apps.e2_adapter.services.optional.codec import e2sm_anr_codec as anr

TS = "2026-10-17T00:01:30.500000+08:00"
METRICS = ("RRU.PrbTotDl", "RLF.DetectedRate", "HO.IntraSys.TooLateRate")


def _rel(src, tgt, ver=1):
    return {"sourceCellNcgi": src, "targetCellGlobalId": tgt, "targetPhysicalCellId": 9, "targetArfcn": 633333,
            "hoValidated": True, "version": ver}


def _sample(cells=("e50:gnb1_c0", "e50:gnb1_c1"), rels_per_cell=3, ghost=True):
    rels = [_rel(c, f"t{c}-{k}") for c in cells for k in range(rels_per_cell)]
    if ghost:
        rels.append(_rel("old:c9", "t-ghost"))
    return {
        "timestamp": TS, "sceneSimMs": 30000, "granularityPeriod": "60s",
        "e2NodeInformation": {
            "servingCells": [{"ncgi": c, "physicalCellId": i, "arfcn": 633333, "a3Offset": 3.0} for i, c in enumerate(cells)],
            "neighbourCellRelations": rels,
            "frequencyRelations": [{"arfcn": 633333}],
            "nrtCapacity": {"limit": 32, "used": rels_per_cell, "usedByCell": {c: rels_per_cell for c in cells}},
            "anrIntraEnabled": True,
            "relationChangeEvents": [{"action": "ADD", "sourceCellNcgi": cells[0], "targetCellGlobalId": "x"},
                                     {"action": "REMOVE", "sourceCellNcgi": "old:c9", "targetCellGlobalId": "y"}],
            "flagChangeEvents": [{"action": "FLAG_SET", "sourceCellNcgi": cells[-1], "targetCellGlobalId": "z", "flag": "noRemove"}],
        },
        "kpmIndication": {
            "cellLevel": {f"{m}.{c}": {"current": 1.0} for m in METRICS for c in cells},
            "perNeighbourRelation": [{"sourceCellNcgi": r["sourceCellNcgi"], "targetCellGlobalId": r["targetCellGlobalId"],
                                      "attByTrigger": {}} for r in rels],
        },
        "e2MessageCopyAggregate": {"measurementReportAggregate": [{"reportedPhysicalCellId": 9}],
                                   "reestablishmentInboundByPreviousPci": []},
        "cgiResolutionSampling": [{"pci": 9}],
        "cccConfigurationEvents": [],
    }


def _decode(payloads):
    return [(json.loads(h), json.loads(zlib.decompress(m))) for h, m in payloads]


def _all(out, path):
    acc = []
    for _, b in out:
        d = b
        for k in path:
            d = (d or {}).get(k)
        acc += d or []
    return acc


class AnrV2Tests(TestCase):
    def test_oid_and_rfd(self) -> None:
        self.assertTrue(anr.ANR_V2_OID.startswith("2.25.") and anr.ANR_V2_OID.endswith(".1.2"))
        self.assertFalse(anr.ANR_V2_OID.startswith("1.3.6.1.4.1.53148"))
        rfd = json.loads(anr.encode_anr_v2_ran_function_description())
        self.assertEqual(rfd["ranFunctionName"]["ranFunctionServiceModelOID"], anr.ANR_V2_OID)
        self.assertEqual([s["ricActionId"] for s in rfd["listOfSupportedReportStyles"]], [0, 2])
        self.assertTrue(rfd["listOfSupportedRICControlStyles"])

    def test_one_report_per_cell_plus_node(self) -> None:
        data = _sample()
        out = _decode(anr.build_anr_v2_payloads(data, sn=7))
        self.assertEqual([h["report"] for h, _ in out], ["cell", "cell", "node"])
        for i, (h, b) in enumerate(out):
            self.assertEqual((h["format"], h["sn"], h["action"], h["report_index"], h["report_count"]), ("DT-ANR-v2", 7, 0, i, 3))
            self.assertEqual(h["timestamp"], TS)
            self.assertGreater(h["timestamp_ms"], 0)
            self.assertEqual((b["timestamp"], b["sceneSimMs"], b["granularityPeriod"]), (TS, 30000, "60s"))
        for h, b in out[:2]:
            c = h["cell"]
            ni = b["e2NodeInformation"]
            self.assertEqual([s["ncgi"] for s in ni["servingCells"]], [c])
            self.assertTrue(ni["neighbourCellRelations"] and all(r["sourceCellNcgi"] == c for r in ni["neighbourCellRelations"]))
            self.assertEqual(ni["nrtCapacity"], {"limit": 32, "used": 3})
            self.assertEqual(sorted(b["kpmIndication"]["cellLevel"]), sorted(f"{m}.{c}" for m in METRICS))
            self.assertTrue(all(x["sourceCellNcgi"] == c for x in b["kpmIndication"]["perNeighbourRelation"]))
        node = out[2][1]
        self.assertEqual(node["e2NodeInformation"]["nrtCapacity"]["usedByCell"], data["e2NodeInformation"]["nrtCapacity"]["usedByCell"])
        self.assertEqual([r["sourceCellNcgi"] for r in node["e2NodeInformation"]["neighbourCellRelations"]], ["old:c9"])
        self.assertEqual(node["cgiResolutionSampling"], [{"pci": 9}])
        self.assertEqual(len(node["cells"]), 2)

    def test_nothing_lost(self) -> None:
        data = _sample()
        out = _decode(anr.build_anr_v2_payloads(data, sn=1))
        ni = data["e2NodeInformation"]
        for path, src in ((("e2NodeInformation", "neighbourCellRelations"), ni["neighbourCellRelations"]),
                          (("e2NodeInformation", "relationChangeEvents"), ni["relationChangeEvents"]),
                          (("e2NodeInformation", "flagChangeEvents"), ni["flagChangeEvents"]),
                          (("kpmIndication", "perNeighbourRelation"), data["kpmIndication"]["perNeighbourRelation"])):
            got = _all(out, path)
            self.assertEqual(sorted(json.dumps(x, sort_keys=True) for x in got), sorted(json.dumps(x, sort_keys=True) for x in src), path)
        keys = [k for _, b in out for k in b["kpmIndication"]["cellLevel"]]
        self.assertEqual(sorted(keys), sorted(data["kpmIndication"]["cellLevel"]))

    def test_large_cell_paged_under_limit(self) -> None:
        data = _sample(cells=("e50:gnb1_c0",), rels_per_cell=400, ghost=False)
        rnd = random.Random(0)   # 不加雜訊的話,重複內容壓縮後會小到不需要分頁
        for x in data["e2NodeInformation"]["neighbourCellRelations"] + data["kpmIndication"]["perNeighbourRelation"]:
            x["noise"] = rnd.getrandbits(64)
        limit = 3000
        payloads = anr.build_anr_v2_payloads(data, sn=2, limit=limit)
        self.assertTrue(all(len(m) <= limit for _, m in payloads))
        out = _decode(payloads)
        pages = [(h, b) for h, b in out if h["report"] == "cell"]
        self.assertGreater(len(pages), 1)
        self.assertEqual([h["page"] for h, _ in pages], list(range(len(pages))))
        self.assertIn("servingCells", pages[0][1]["e2NodeInformation"])
        self.assertTrue(all(b["timestamp"] == TS for _, b in pages))
        self.assertEqual(len(_all(pages, ("e2NodeInformation", "neighbourCellRelations"))), 400)
        self.assertEqual(len(_all(pages, ("kpmIndication", "perNeighbourRelation"))), 400)

    def test_change_reports_per_source_cell(self) -> None:
        old = _sample()
        prev = anr.relation_versions(old)
        self.assertEqual(anr.build_anr_v2_change_payloads(old, prev, sn=1), [])
        new = _sample()
        rels = new["e2NodeInformation"]["neighbourCellRelations"]
        rels.append(_rel("e50:gnb1_c0", "added-1"))                     # c0:新增
        rels[:] = [r for r in rels if r["targetCellGlobalId"] != "te50:gnb1_c1-0"]   # c1:移除
        for r in rels:
            if r["targetCellGlobalId"] == "te50:gnb1_c1-1":
                r["version"] = 2                                            # c1:版本變動
        out = _decode(anr.build_anr_v2_change_payloads(new, prev, sn=5))
        self.assertEqual([h["cell"] for h, _ in out], ["e50:gnb1_c0", "e50:gnb1_c1"])
        self.assertTrue(all(h["action"] == 2 and h["report"] == "change" and h["report_count"] == 2 for h, _ in out))
        c0, c1 = out[0][1], out[1][1]
        self.assertEqual(c0["changeMarks"]["added"], ["e50:gnb1_c0->added-1"])
        self.assertEqual(c1["changeMarks"]["removed"], ["e50:gnb1_c1->te50:gnb1_c1-0"])
        self.assertEqual(c1["changeMarks"]["versionBumped"], ["e50:gnb1_c1->te50:gnb1_c1-1"])
        self.assertEqual(len(c0["e2NodeInformation"]["neighbourCellRelations"]), 4)
        self.assertTrue(all(r["sourceCellNcgi"] == "e50:gnb1_c1" for r in c1["e2NodeInformation"]["neighbourCellRelations"]))

    def test_v1_unchanged(self) -> None:
        self.assertEqual((anr.ANR_RAN_FUNCTION_ID, anr.ANR_OID), (6, "1.3.6.1.4.1.53148.1.1.2.6"))
        hdr, _ = anr.build_indication_payloads(_sample(), sn=3)[0]
        self.assertEqual(json.loads(hdr)["format"], "DT-ANR-v1")
