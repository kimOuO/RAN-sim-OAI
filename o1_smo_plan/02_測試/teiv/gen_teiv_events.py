#!/usr/bin/env python3
"""
產生 TEIV(o-ran-sc/smo-teiv 0.3.0)拓樸匯入用的 CloudEvent 內容(JSON body + kafka header 行)。
資料來源:DT run-orchestrator `FieldReader/config`(靜態場域設定,含 e2_identities 與 cells)。
用法:
  python3 gen_teiv_events.py --field-id scene-… [--orch http://127.0.0.1:8302] [--mode create|merge|delete]
        [--ric-meid gnb_ric-dt-71] --out teiv_<name>.json
輸出:
  <out>.json         結構化 CloudEvent(structured mode,content-type application/cloudevents+json)
  <out>.body.json    只有 data(binary mode 用)
  <out>.headers.txt  binary mode 的 ce_* header(kafka-console-producer parse.headers 格式)
規則(依 smo-teiv 原始碼):id 只能含 [-!$&'()*+,:;=._~0-9a-zA-Z];relationship 的 sourceIds ≥2;
  NRCellCU 用 plmnId(小寫 p),Function 用 pLMNId / dUpLMNId;mcc/mnc 為字串;NRCellDU 沒有 PLMN。
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
import datetime as dt
import urllib.request

RAN = "o-ran-smo-teiv-ran"
OAM = "o-ran-smo-teiv-oam"
REL = "o-ran-smo-teiv-rel-oam-ran"


def dn(*parts: str) -> str:
    return "urn:3gpp:dn:" + ",".join(parts)


def rel_id(rtype: str, a: str, b: str) -> str:
    # 只留允許字元
    key = (a.split("dn:")[-1] + "_" + b.split("dn:")[-1]).replace(",", ".").replace("/", "_")
    return f"urn:oran:smo:teiv:{rtype}={key}"


def fetch_config(orch: str, field_id: str) -> dict:
    req = urllib.request.Request(f"{orch}/api/v0.1/Run_orchestrator/Agent_api/FieldReader/config",
                                 data=json.dumps({"field_id": field_id}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        body = json.load(r)
    return body.get("data", body)


def build(cfg: dict, mode: str, ric_meid: str | None) -> dict:
    ents: dict[str, list] = {}
    rels: dict[str, list] = {}

    def add(store, key, item):
        store.setdefault(key, []).append(item)

    ids = {e["node_id"]: e for e in cfg.get("e2_identities", [])}
    if not ids:  # FieldReader/list 才有 e2_identities;config 沒有時從 cells 推
        for c in cfg.get("cells", []):
            ids.setdefault(c["gnb_id"], {"node_id": c["gnb_id"], "meid": c["ran_name"], "gnb_id_int": None,
                                          "plmn": {"mcc": "208", "mnc": "095"}, "cells": []})
    cells_by_gnb: dict[str, list] = {}
    for c in cfg.get("cells", []):
        cells_by_gnb.setdefault(c["gnb_id"], []).append(c)

    for node_id, e in ids.items():
        meid = e["meid"]
        mcc, mnc = e["plmn"]["mcc"], str(int(e["plmn"]["mnc"]))  # 208 / 95
        gnb_id = e.get("gnb_id_int") or int(meid.split("_")[-1], 16)
        du_n = int(e.get("gnb_du_id", 1))
        me = dn(f"ManagedElement={meid}")
        me_du = dn(f"ManagedElement={meid}_du{du_n}")              # O1 的 DU ME(adapter 一顆一種 Function,所以 DU 是獨立 ME)
        cucp = dn(f"ManagedElement={meid}", "OCUCPFunction=0")
        odu = dn(f"ManagedElement={meid}_du{du_n}", f"ODUFunction={du_n}")
        if mode == "delete":
            add(ents, f"{OAM}:ManagedElement", {"id": me})
            add(ents, f"{OAM}:ManagedElement", {"id": me_du})
            add(ents, f"{RAN}:OCUCPFunction", {"id": cucp})
            add(ents, f"{RAN}:ODUFunction", {"id": odu})
        else:
            add(ents, f"{OAM}:ManagedElement", {"id": me, "sourceIds": [me, f"urn:dt:run-orchestrator:{node_id}"]})
            add(ents, f"{OAM}:ManagedElement", {"id": me_du, "sourceIds": [me_du, f"urn:dt:run-orchestrator:{node_id}"]})
            add(ents, f"{RAN}:OCUCPFunction", {"id": cucp, "sourceIds": [cucp, dn(f"ManagedElement={meid}", "GNBCUCPFunction=0")],
                "attributes": {"gNBCUName": meid, "gNBId": gnb_id, "gNBIdLength": 22, "pLMNId": {"mcc": mcc, "mnc": mnc}}})
            add(ents, f"{RAN}:ODUFunction", {"id": odu, "sourceIds": [odu, dn(f"ManagedElement={meid}_du{du_n}", f"GNBDUFunction={du_n}")],
                "attributes": {"gNBDUId": du_n, "gNBId": gnb_id, "gNBIdLength": 22, "dUpLMNId": {"mcc": mcc, "mnc": mnc}}})
            add(rels, f"{REL}:MANAGEDELEMENT_MANAGES_OCUCPFUNCTION",
                {"id": rel_id("MANAGEDELEMENT_MANAGES_OCUCPFUNCTION", me, cucp), "aSide": me, "bSide": cucp, "sourceIds": [me, cucp]})
            add(rels, f"{REL}:MANAGEDELEMENT_MANAGES_ODUFUNCTION",
                {"id": rel_id("MANAGEDELEMENT_MANAGES_ODUFUNCTION", me_du, odu), "aSide": me_du, "bSide": odu, "sourceIds": [me_du, odu]})
            add(rels, f"{RAN}:ODUFUNCTION_F1CLINK_OCUCPFUNCTION",
                {"id": rel_id("ODUFUNCTION_F1CLINK_OCUCPFUNCTION", odu, cucp), "aSide": odu, "bSide": cucp, "sourceIds": [odu, cucp]})
            if ric_meid:
                ric = dn(f"ManagedElement={ric_meid}", "NearRTRICFunction=1")
                add(rels, f"{RAN}:OCUCPFUNCTION_E2LINK_NEARRTRICFUNCTION",
                    {"id": rel_id("OCUCPFUNCTION_E2LINK_NEARRTRICFUNCTION", cucp, ric), "aSide": cucp, "bSide": ric, "sourceIds": [cucp, ric]})
                add(rels, f"{RAN}:ODUFUNCTION_E2LINK_NEARRTRICFUNCTION",
                    {"id": rel_id("ODUFUNCTION_E2LINK_NEARRTRICFUNCTION", odu, ric), "aSide": odu, "bSide": ric, "sourceIds": [odu, ric]})
        for i, c in enumerate(cells_by_gnb.get(node_id, [])):
            local = int(c.get("local_cell_id", i))
            nci = int(c.get("nr_cell_identity") or ((gnb_id << 14) | local))
            ncu = dn(f"ManagedElement={meid}", "OCUCPFunction=0", f"NRCellCU={local}")
            ndu = dn(f"ManagedElement={meid}_du{du_n}", f"ODUFunction={du_n}", f"NRCellDU={local}")
            nsc = dn(f"ManagedElement={meid}_du{du_n}", f"ODUFunction={du_n}", f"NRSectorCarrier={local}")
            du_side = (i == 0)   # O1 的 DU ME 目前只呈現第一個 cell(adapter 單 NRCellDU);TEIV 與之對齊
            if mode == "delete":
                add(ents, f"{RAN}:NRCellCU", {"id": ncu})
                if du_side:
                    add(ents, f"{RAN}:NRCellDU", {"id": ndu}); add(ents, f"{RAN}:NRSectorCarrier", {"id": nsc})
                continue
            tac = int(c.get("tac", 40960))
            add(ents, f"{RAN}:NRCellCU", {"id": ncu, "sourceIds": [ncu, dn(f"ManagedElement={meid}", "GNBCUCPFunction=0", f"NRCellCU={local}")],
                "attributes": {"cellLocalId": local, "nCI": nci, "nRTAC": tac, "plmnId": {"mcc": mcc, "mnc": mnc}}})
            add(rels, f"{RAN}:OCUCPFUNCTION_PROVIDES_NRCELLCU",
                {"id": rel_id("OCUCPFUNCTION_PROVIDES_NRCELLCU", cucp, ncu), "aSide": cucp, "bSide": ncu, "sourceIds": [cucp, ncu]})
            if not du_side:
                continue
            add(ents, f"{RAN}:NRCellDU", {"id": ndu, "sourceIds": [ndu, dn(f"ManagedElement={meid}_du{du_n}", f"GNBDUFunction={du_n}", f"NRCellDU={local}")],
                "attributes": {"cellLocalId": local, "nCI": nci, "nRPCI": int(c.get("pci", 0)), "nRTAC": tac}})
            arfcn = int(c.get("arfcn", 633333)); bw = int(round(float(c.get("bandwidth_mhz", 40))))
            add(ents, f"{RAN}:NRSectorCarrier", {"id": nsc, "sourceIds": [nsc, dn(f"ManagedElement={meid}_du{du_n}", f"GNBDUFunction={du_n}", f"NRSectorCarrier={local}")],
                "attributes": {"arfcnDL": arfcn, "arfcnUL": arfcn, "frequencyDL": int(float(c.get("center_frequency_ghz", 3.5)) * 1000),
                               "frequencyUL": int(float(c.get("center_frequency_ghz", 3.5)) * 1000), "bSChannelBwDL": bw}})
            add(rels, f"{RAN}:ODUFUNCTION_PROVIDES_NRCELLDU",
                {"id": rel_id("ODUFUNCTION_PROVIDES_NRCELLDU", odu, ndu), "aSide": odu, "bSide": ndu, "sourceIds": [odu, ndu]})
            add(rels, f"{RAN}:ODUFUNCTION_PROVIDES_NRSECTORCARRIER",
                {"id": rel_id("ODUFUNCTION_PROVIDES_NRSECTORCARRIER", odu, nsc), "aSide": odu, "bSide": nsc, "sourceIds": [odu, nsc]})
            add(rels, f"{RAN}:NRCELLDU_USES_NRSECTORCARRIER",
                {"id": rel_id("NRCELLDU_USES_NRSECTORCARRIER", ndu, nsc), "aSide": ndu, "bSide": nsc, "sourceIds": [ndu, nsc]})
    data = {"entities": [{k: v} for k, v in ents.items()]}
    if rels:
        data["relationships"] = [{k: v} for k, v in rels.items()]
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--field-id", required=True)
    ap.add_argument("--orch", default="http://127.0.0.1:8302")
    ap.add_argument("--mode", default="create", choices=["create", "merge", "delete"])
    ap.add_argument("--ric-meid", default="ric-dt-71", help="Near-RT RIC 的 ManagedElement 名(預設 ric-dt-71 = 10.3.0.71 的 RIC-A;傳空字串則不加 E2LINK)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--me-map", default=None, help="orchestrator 的 notify_added_*.md 或 me_map.json,用來取得每個 meid 的 gNB-DU id(O1 的 _du<N>)")
    a = ap.parse_args()
    cfg = fetch_config(a.orch, a.field_id)
    # e2_identities 在 FieldReader/list 才有,補抓
    if not cfg.get("e2_identities"):
        req = urllib.request.Request(f"{a.orch}/api/v0.1/Run_orchestrator/Agent_api/FieldReader/list", data=b"{}", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            for f in json.load(r)["data"]["fields"]:
                if f["field_id"] == a.field_id:
                    cfg["e2_identities"] = f["e2_identities"]
    if a.me_map:
        import re
        txt = open(a.me_map, encoding="utf-8").read()
        dumap = {}
        try:
            dumap = {k: int(v) for k, v in json.loads(txt).items()}
        except Exception:  # markdown 表格:抓 `gnb_..._du<N>`
            for m in re.finditer(r"(gnb_\d{3}_\d{3}_[0-9a-f]{6})_du(\d+)", txt):
                dumap[m.group(1)] = int(m.group(2))
        for e in cfg.get("e2_identities", []):
            if e["meid"] in dumap:
                e["gnb_du_id"] = dumap[e["meid"]]
    if a.mode == "delete":
        # delete 事件:entity 與 relationship 都只留 id(依 smo-teiv 規格),從 create 的完整結構裁下來
        full = build(cfg, "create", a.ric_meid)
        data = {"entities": [{k: [{"id": it["id"]} for it in v] for k, v in d.items()} for d in full["entities"]],
                "relationships": [{k: [{"id": it["id"]} for it in v] for k, v in d.items()} for d in full.get("relationships", [])]}
    else:
        data = build(cfg, a.mode, a.ric_meid)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ce = {"specversion": "1.0", "id": str(uuid.uuid4()), "source": "ransim-dt:run-orchestrator",
          "type": f"topology-inventory-ingestion.{a.mode}", "datacontenttype": "application/json",
          "dataschema": f"topology-inventory-ingestion:events:{a.mode}:1.0.0", "time": now, "data": data}
    json.dump(ce, open(a.out, "w"), indent=2, ensure_ascii=False)
    json.dump(data, open(a.out.replace(".json", ".body.json"), "w"), indent=2, ensure_ascii=False)
    hdr = f"ce_specversion:::1.0,ce_id:::{ce['id']},ce_source:::{ce['source']},ce_type:::{ce['type']},content-type:::application/json,ce_time:::{now},ce_dataschema:::{ce['dataschema']}"
    open(a.out.replace(".json", ".headers.txt"), "w").write(hdr + "\n")
    n_e = sum(len(v) for d in data["entities"] for v in d.values()); n_r = sum(len(v) for d in data.get("relationships", []) for v in d.values())
    print(f"wrote {a.out}: {n_e} entities, {n_r} relationships", file=sys.stderr)


if __name__ == "__main__":
    main()
