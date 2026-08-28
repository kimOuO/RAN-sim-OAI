#!/usr/bin/env python3
"""全場覆蓋 / 壓制區地圖 —— 一次把「這個場誰是霸凌天線」講清楚。

為什麼要有這支:Q4 的 822-RLF 風暴與 Q5 的「mid 是弱天線」都是**跑掉一輪
之後**才用逐點探測撞出來的。azimuth_deg 不轉場型、per-scene 常有一顆
+26dB 的熱天線 —— 幾何不能用設計圖紙推,只能實測。這支把 probe_positions
的單線掃描升級成整場網格,佈場前跑一次,站位/走廊直接看圖挑。

用法(場景必須已載入 physics):
  python3 scripts/field_survey.py --x -400:400:25 --z -60:0:20 [--tx name=dbm ...]

輸出每格:最強 cell、對次強的優勢 dB、以及三個判定:
  BULLY  最強者領先 >10dB(獨佔區,別的 cell 在這裡永遠搶不到人)
  EDGE   領先 <3dB(A3 窗區,換手/乒乓都發生在這)
  DEAD   最強 RSRP < -100(量測門檻外,UE 在這裡是聾的)
預設 tx=30dBm;劇本功率不同時用 --tx 覆蓋(power_dbm 已接線,Q4 實證)。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request

PHYSICS = "http://localhost:8104/api/v0.1/Physics/RanCalc/PathSolver/compute"


def _rng(spec: str) -> list[float]:
    a = [float(x) for x in spec.split(":")]
    if len(a) == 1:
        return a
    lo, hi, step = a
    out, v = [], lo
    while v <= hi + 1e-9:
        out.append(round(v, 3))
        v += step
    return out


def probe(points):
    body = {"ue_positions": [
        {"id": f"g{i}", "position": list(p), "velocity": [0.0, 0.0, 0.0]}
        for i, p in enumerate(points)]}
    req = urllib.request.Request(PHYSICS, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--x", required=True, help="起:迄:步長")
    ap.add_argument("--y", default="1.5")
    ap.add_argument("--z", default="-40", help="起:迄:步長 或單值")
    ap.add_argument("--tx", action="append", default=[],
                    help="cell 名=功率dBm(可多次;預設全部 30)")
    args = ap.parse_args()

    txmap = {}
    for t in args.tx:
        k, v = t.split("=")
        txmap[k.strip()] = float(v)

    pts = [(x, y, z) for z in _rng(args.z) for y in _rng(args.y) for x in _rng(args.x)]
    # PathSolver 一次吃太多點會逾時 —— 分批
    gains_all: dict[str, dict] = {}
    B = 40
    for i in range(0, len(pts), B):
        batch = pts[i:i + B]
        data = (probe(batch).get("data") or {}).get("path_gain") or {}
        for j, p in enumerate(batch):
            gains_all[json.dumps(p)] = data.get(f"g{j}") or {}

    def dbm(cell_label: str, g: float) -> float:
        name = cell_label.split("#")[0]
        tx = txmap.get(name, 30.0)
        return tx + 10.0 * math.log10(g) if g and g > 0 else float("-inf")

    stats = {"BULLY": 0, "EDGE": 0, "DEAD": 0, "OK": 0}
    own: dict[str, int] = {}
    print(f"{'位置':<24}{'最強':<12}{'RSRP':>8}{'次強':<12}{'領先':>7}  判定")
    print("-" * 78)
    for key, per_cell in gains_all.items():
        p = json.loads(key)
        lv = sorted(((dbm(c, float(g)), c) for c, g in per_cell.items()), reverse=True)
        if not lv or lv[0][0] == float("-inf"):
            tag = "DEAD"
            print(f"{str(tuple(p)):<24}{'—':<12}{'—':>8}{'—':<12}{'—':>7}  DEAD")
        else:
            best_dbm, best = lv[0]
            second_dbm, second = lv[1] if len(lv) > 1 else (float("-inf"), "—")
            lead = best_dbm - second_dbm
            if best_dbm < -100:
                tag = "DEAD"
            elif lead > 10:
                tag = "BULLY"
            elif lead < 3:
                tag = "EDGE"
            else:
                tag = "OK"
            own[best] = own.get(best, 0) + 1
            print(f"{str(tuple(p)):<24}{best:<12}{best_dbm:>8.1f}{second:<12}"
                  f"{lead:>7.1f}  {tag}")
        stats[tag] += 1

    total = sum(stats.values()) or 1
    print("-" * 78)
    print("覆蓋佔比:", {k: f"{v} ({100*v//total}%)" for k, v in stats.items()})
    print("各 cell 稱王格數:", dict(sorted(own.items(), key=lambda kv: -kv[1])))
    if stats["BULLY"] * 2 > total:
        print("⚠️ 半數以上是獨佔區 —— 這個場有霸凌天線,窄窗題請先跑 probe_positions 確認")
    return 0


if __name__ == "__main__":
    sys.exit(main())
