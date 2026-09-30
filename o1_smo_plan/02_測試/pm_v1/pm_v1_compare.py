#!/usr/bin/env python3
"""
PM-V1 對值:轉接程式(facade)每次回覆 o1 stats 時印的 STAT 紀錄 → 依 o1-adapter 的算法
(週期內取整數平均、MaxActiveUe 取最大)算出預期值,與 adapter 產出的 XML 比對。
用法: pm_v1_compare.py <rid> <HHMM 起> <HHMM 迄> [--date 2026-09-30] [--save-xml DIR]
"""
import argparse, re, subprocess, json, os
import xml.etree.ElementTree as ET

STAT = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ INFO STAT du cell=\S+ pci=\S+ num_ues=(\d+) load=(\d+) sum_dl_kbps=(\d+) sum_ul_kbps=(\d+)")
NS = {"m": "http://www.3gpp.org/ftp/specs/archive/32_series/32.435#measCollec"}


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rid"); ap.add_argument("start"); ap.add_argument("end")
    ap.add_argument("--date", default="2026-09-30"); ap.add_argument("--save-xml", default=None)
    a = ap.parse_args()
    t0 = f"{a.date} {a.start[:2]}:{a.start[2:]}:00"; t1 = f"{a.date} {a.end[:2]}:{a.end[2:]}:00"
    names = sorted(n for n in sh("docker", "ps", "--format", "{{.Names}}").split() if n.startswith(f"o1adapter-du-{a.rid}-"))
    rows = []
    for ad in names:
        idx = ad.rsplit("-", 1)[1]
        fname = next((f for f in sh("docker", "exec", ad, "ls", "/ftp").split() if f".{a.start}+0000-{a.end}+0000_" in f), None)
        if not fname:
            print(ad, "no file for window"); continue
        xml = sh("docker", "exec", ad, "cat", f"/ftp/{fname}")
        if a.save_xml:
            os.makedirs(a.save_xml, exist_ok=True); open(os.path.join(a.save_xml, fname), "w").write(xml)
        root = ET.fromstring(xml)
        types = {e.get("p"): e.text for e in root.iterfind(".//m:measType", NS)}
        got = {types[e.get("p")]: int(e.text) for e in root.iterfind(".//m:measValue/m:r", NS)}
        suspect = root.find(".//m:measValue/m:suspect", NS)
        logs = subprocess.run(["docker", "logs", f"o1facade-{a.rid}-{idx}"], capture_output=True, text=True)
        s = [tuple(map(int, m.groups()[1:])) for m in (STAT.match(l) for l in (logs.stdout + logs.stderr).splitlines()) if m and t0 <= m.group(1) < t1]
        n = len(s)
        exp = {"DRB.MeanActiveUeDl": sum(x[0] for x in s) // n, "DRB.MaxActiveUeDl": max(x[0] for x in s),
               "RRU.PrbTotDl": sum(x[1] for x in s) // n, "DRB.UEThpDl": sum(x[2] for x in s) // n, "DRB.UEThpUl": sum(x[3] for x in s) // n}
        exp["DRB.MeanActiveUeUl"] = exp["DRB.MeanActiveUeDl"]; exp["DRB.MaxActiveUeUl"] = exp["DRB.MaxActiveUeDl"]
        frac = {"ue_mean": round(sum(x[0] for x in s) / n, 2), "ue_min": min(x[0] for x in s), "load_mean": round(sum(x[1] for x in s) / n, 1)}
        rows.append({"file": fname, "samples": n, "suspect": suspect.text if suspect is not None else None, "expected": exp, "xml": got, "detail": frac,
                     "diff": {k: got.get(k, None) - v for k, v in exp.items() if got.get(k) is not None}})
    print(json.dumps(rows, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
