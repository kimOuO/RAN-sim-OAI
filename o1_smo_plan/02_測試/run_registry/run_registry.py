#!/usr/bin/env python3
"""
O1 run 對照表查詢工具:runId ↔ 劇本 ↔ ME ↔ 起訖時間。

SMO 的 PM(InfluxDB)與告警只帶 ME 名稱,ME 名稱又會被不同 run、不同劇本重用。
要「以劇本為單位」收資料,用這份對照把劇本換成一組(ME、時間區間)。

資料來源(都在 PER_RUN_LOG_DIR,主機路徑 ran-emulation-runtime/run_logs/):
  _o1_run_registry.jsonl           編排服務每次啟動 / 停止各寫一行(2026-10-01 起)
  _o1_run_registry.backfill.jsonl  由 `backfill` 從舊的 notify_added / notify_removed 通知檔補回

用法:
  run_registry.py backfill [--scenario-map rid=劇本 …]   補回上線前的 run(可重跑,會整份重寫)
  run_registry.py list [--scenario S] [--since ISO] [--md]  每次執行一列
  run_registry.py windows --scenario S                      每個 ME 的時間區間(CSV)
  run_registry.py flux --scenario S [--bucket pm-logg-bucket]   每次執行的 InfluxDB Flux 查詢
"""
import argparse, datetime as dt, glob, json, os, re, sys

LOG_DIR = os.environ.get("RUN_LOG_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../ran-emulation-runtime/run_logs"))
REG = os.path.join(LOG_DIR, "_o1_run_registry.jsonl")
BACK = os.path.join(LOG_DIR, "_o1_run_registry.backfill.jsonl")
# rid 跟著場景,所以舊 run 的劇本可以由 rid 決定(2026-09-29、09-30 實際用過的兩個場景)
DEFAULT_SCENARIO = {"c9ad0776": "corridor24_00_08", "00bba8b4": "corridor24_16_24"}
ROW = re.compile(r"\| `(gnb_\d{3}_\d{3}_[0-9a-f]{6})` \| `(gnb_\S+?_du\d+)` \| \S+?:(\d+) \| \S+?:(\d+) \|")


def _iso(name: str) -> str:
    m = re.search(r"(\d{4}-\d\d-\d\d)T(\d\d)(\d\d)(\d\d)Z", name)
    return f"{m.group(1)}T{m.group(2)}:{m.group(3)}:{m.group(4)}Z"


def backfill(scn_map: dict) -> int:
    first_live = None
    if os.path.exists(REG):
        with open(REG, encoding="utf-8") as f:
            ts = [json.loads(l)["ts"] for l in f if l.strip()]
        first_live = min(ts) if ts else None
    out = []
    for d in sorted(glob.glob(os.path.join(LOG_DIR, "*", "o1"))):
        rid = os.path.basename(os.path.dirname(d))
        evs = sorted((_iso(os.path.basename(p)), "start" if "notify_added" in p else "stop", p)
                     for p in glob.glob(os.path.join(d, "notify_*.md")))
        open_tag = None
        for ts, kind, path in evs:
            if first_live and ts >= first_live:
                break   # 之後的由編排服務自己記
            if kind == "start":
                if open_tag:   # 前一次沒有移除通知:自動重啟,或編排服務重啟後漏記
                    out.append({"ts": ts, "event": "stop", "runId": open_tag, "rid": rid, "scenarioId": scn_map.get(rid, "unknown"),
                                "reason": "inferred", "source": "backfill"})
                txt = open(path, encoding="utf-8").read()
                mes = [{"gnb": "", "cucp": m.group(1), "du": m.group(2), "netconf_cucp": int(m.group(3)), "netconf_du": int(m.group(4))}
                       for m in ROW.finditer(txt)]
                open_tag = f"{rid}-{ts.replace('-', '').replace(':', '')}"
                out.append({"ts": ts, "event": "start", "runId": open_tag, "rid": rid, "scene_run_uuid": "",
                            "scenarioId": scn_map.get(rid, "unknown"), "mes": mes, "source": "backfill"})
            elif open_tag:
                out.append({"ts": ts, "event": "stop", "runId": open_tag, "rid": rid, "scenarioId": scn_map.get(rid, "unknown"),
                            "reason": "normal", "source": "backfill"})
                open_tag = None
    with open(BACK, "w", encoding="utf-8") as f:
        for r in sorted(out, key=lambda r: r["ts"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(out)


def load() -> list[dict]:
    """回傳每次執行一筆:{runId, rid, scenarioId, start, stop, reason, mes, source}。"""
    recs = []
    for p in (BACK, REG):
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                recs += [json.loads(l) for l in f if l.strip()]
    recs.sort(key=lambda r: r["ts"])
    runs, by_rid_open = [], {}
    for r in recs:
        if r["event"] == "start":
            prev = by_rid_open.get(r["rid"])
            if prev and not prev["stop"]:          # 同一 rid 又起了一次但前一次沒有 stop 紀錄
                prev["stop"], prev["reason"] = r["ts"], "inferred"
            run = {"runId": r["runId"], "rid": r["rid"], "scenarioId": r.get("scenarioId", "unknown"), "start": r["ts"], "stop": None,
                   "reason": None, "mes": r.get("mes", []), "source": r.get("source", "orchestrator")}
            runs.append(run); by_rid_open[r["rid"]] = run
        else:
            run = next((x for x in reversed(runs) if x["runId"] == r["runId"] and not x["stop"]), None)
            if run:
                run["stop"], run["reason"] = r["ts"], r.get("reason", "normal")
    return runs


def _filter(runs, a):
    if a.scenario:
        runs = [r for r in runs if r["scenarioId"] == a.scenario]
    if getattr(a, "since", None):
        runs = [r for r in runs if r["start"] >= a.since]
    return runs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backfill"); b.add_argument("--scenario-map", nargs="*", default=[])
    l = sub.add_parser("list"); l.add_argument("--scenario"); l.add_argument("--since"); l.add_argument("--md", action="store_true")
    w = sub.add_parser("windows"); w.add_argument("--scenario", required=True)
    x = sub.add_parser("flux"); x.add_argument("--scenario", required=True); x.add_argument("--bucket", default="pm-logg-bucket")
    a = ap.parse_args()
    if a.cmd == "backfill":
        m = dict(DEFAULT_SCENARIO); m.update(dict(kv.split("=", 1) for kv in a.scenario_map))
        print(f"backfill: {backfill(m)} records → {BACK}")
        return
    runs = _filter(load(), a)
    if a.cmd == "list":
        if a.md:
            print("| runId | 劇本 | 開始(UTC) | 結束(UTC) | 結束原因 | DU ME | 來源 |\n|---|---|---|---|---|---|---|")
        for r in runs:
            dus = ", ".join(m["du"] for m in r["mes"])
            row = [r["runId"], r["scenarioId"], r["start"], r["stop"] or "(進行中或未記錄)", r["reason"] or "", dus, r["source"]]
            print(("| " + " | ".join(row) + " |") if a.md else "\t".join(row))
    elif a.cmd == "windows":
        print("runId,scenarioId,me,role,start,stop")
        for r in runs:
            for m in r["mes"]:
                print(",".join([r["runId"], r["scenarioId"], m["cucp"], "CU-CP", r["start"], r["stop"] or ""]))
                print(",".join([r["runId"], r["scenarioId"], m["du"], "DU", r["start"], r["stop"] or ""]))
    elif a.cmd == "flux":
        # PM 檔每 900 秒一份、時間戳是週期結束;帶 suspect 的頭尾不完整週期不會入庫
        for r in runs:
            stop = r["stop"] or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            pat = "|".join(re.escape(m["du"]) for m in r["mes"])
            print(f"// {r['runId']}  {r['scenarioId']}  {r['start']} → {stop}")
            print(f'from(bucket: "{a.bucket}")\n  |> range(start: {r["start"]}, stop: {stop})\n'
                  f'  |> filter(fn: (r) => r._measurement =~ /ManagedElement=({pat}),/)\n')


if __name__ == "__main__":
    main()
