#!/usr/bin/env python3
"""
只產生 TEIV 的連線關係(官方 ncmp-to-teiv-adapter 產不出的部分):
  OCUCPFUNCTION_E2LINK_NEARRTRICFUNCTION、ODUFUNCTION_E2LINK_NEARRTRICFUNCTION、ODUFUNCTION_F1CLINK_OCUCPFUNCTION
aSide 用 adapter 的 id 形式 `urn:oran:smo:teiv:ManagedElement=<meid>,GNBCUCPFunction=0` / `…_du<N>,GNBDUFunction=<N>`;
RIC 用 `urn:3gpp:dn:ManagedElement=ric-dt-71,NearRTRICFunction=1`(DT 事件檔保留的物件)。
create:一個檔;delete:每條 relationship 一個檔(TEIV 0.3.0 多筆 delete 會卡住)。
用法:
  gen_teiv_links.py --me gnb_208_095_000e00:1 [--me gnb_208_095_000e10:1 …] --out-prefix teiv_links_e00
  或 --me-map <notify_added.md|me_map.json>
"""
import argparse, json, re, uuid, datetime as dt

RAN = "o-ran-smo-teiv-ran"
RIC = "urn:3gpp:dn:ManagedElement=ric-dt-71,NearRTRICFunction=1"


def rel_id(t, a, b):
    return f"urn:oran:smo:teiv:{t}=" + (a.split(":")[-1] + "_" + b.split(":")[-1]).replace(",", ".").replace("/", "_")


def links(meid: str, du_n: int, ric: str) -> list[tuple[str, dict]]:
    cucp = f"urn:oran:smo:teiv:ManagedElement={meid},GNBCUCPFunction=0"
    odu = f"urn:oran:smo:teiv:ManagedElement={meid}_du{du_n},GNBDUFunction={du_n}"
    out = []
    if ric:
        out.append((f"{RAN}:OCUCPFUNCTION_E2LINK_NEARRTRICFUNCTION", {"id": rel_id("OCUCPFUNCTION_E2LINK_NEARRTRICFUNCTION", cucp, ric), "aSide": cucp, "bSide": ric, "sourceIds": [cucp, ric]}))
        out.append((f"{RAN}:ODUFUNCTION_E2LINK_NEARRTRICFUNCTION", {"id": rel_id("ODUFUNCTION_E2LINK_NEARRTRICFUNCTION", odu, ric), "aSide": odu, "bSide": ric, "sourceIds": [odu, ric]}))
    out.append((f"{RAN}:ODUFUNCTION_F1CLINK_OCUCPFUNCTION", {"id": rel_id("ODUFUNCTION_F1CLINK_OCUCPFUNCTION", odu, cucp), "aSide": odu, "bSide": cucp, "sourceIds": [odu, cucp]}))
    return out


def ce(mode, data):
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"specversion": "1.0", "id": str(uuid.uuid4()), "source": "ransim-dt:run-orchestrator",
            "type": f"topology-inventory-ingestion.{mode}", "datacontenttype": "application/json",
            "dataschema": f"topology-inventory-ingestion:events:{mode}:1.0.0", "time": now, "data": data}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--me", action="append", default=[], help="meid:du_id,可重複")
    ap.add_argument("--me-map", default=None)
    ap.add_argument("--ric", default=RIC, help="空字串則不產 E2LINK")
    ap.add_argument("--out-prefix", required=True)
    a = ap.parse_args()
    mes = [(m.split(":")[0], int(m.split(":")[1]) if ":" in m else 1) for m in a.me]
    if a.me_map:
        txt = open(a.me_map, encoding="utf-8").read()
        try:
            mes += [(k, int(v)) for k, v in json.loads(txt).items()]
        except Exception:
            mes += [(m.group(1), int(m.group(2))) for m in re.finditer(r"(gnb_\d{3}_\d{3}_[0-9a-f]{6})_du(\d+)", txt)]
    allrels = [r for meid, du in mes for r in links(meid, du, a.ric)]
    grouped: dict[str, list] = {}
    for k, v in allrels:
        grouped.setdefault(k, []).append(v)
    create = ce("create", {"entities": [], "relationships": [{k: v} for k, v in grouped.items()]})
    json.dump(create, open(f"{a.out_prefix}.create.json", "w"), indent=2)
    for i, (k, v) in enumerate(allrels, 1):
        json.dump(ce("delete", {"entities": [], "relationships": [{k: [{"id": v["id"]}]}]}), open(f"{a.out_prefix}.delete.{i:02d}.json", "w"), indent=2)
    print(f"{a.out_prefix}: {len(allrels)} relationships → 1 create + {len(allrels)} delete files")


if __name__ == "__main__":
    main()
