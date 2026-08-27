#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""改 UE 位置前的強制實測 —— 用 PathSolver 掃出真實訊號差,不准用幾何估算。

為什麼要有這支:2026-08-26 第 7 題連壞三次,每一次的直接原因都是同一個 ——
我用「兩點距離 + 天線朝向」估算增益,估出 3.5 dB,實測是 12.6 dB。
坑目錄第 3 條早就寫著「訊號差一律 PathSolver 實測」,但規則寫在紙上沒有人擋,
所以照樣會犯。這支把規則變成一道會擋人的閘:掃不出符合窗的位置就 exit 1,
不會給你一個「看起來可以」的答案。

窄窗題(第 7、10 題那種「A3 要觸發但不能掉線」)的可用區間很窄:
    觸發窗:目標 − 服務 > a3Offset + hysteresis   ← 太小不換手
    存活窗:換過去之後訊號要還活著              ← 太大代表原本已經快斷線
兩者夾出來通常只有 1.5~4.5 dB。憑估算命中的機率很低,而且錯了要花半小時才看得出來。

用法:
    python3 scripts/probe_positions.py --serving s07_c0 --target n33_c0 \
        --x -120:-60:5 --y 0 --z 1.5 --window 1.5:4.5

輸出每個候選點的實測增益,並標出落在窗內的位置;一個都沒有就 exit 1。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request

PHYSICS = "http://localhost:8104/api/v0.1/Physics/RanCalc/PathSolver/compute"


def _rng(spec: str) -> list[float]:
    """'-120:-60:5' → [-120,-115,...,-60];'0' → [0]。"""
    parts = [float(x) for x in spec.split(":")]
    if len(parts) == 1:
        return parts
    lo, hi, step = parts if len(parts) == 3 else (*parts, 1.0)
    n = int(round((hi - lo) / step))
    return [round(lo + i * step, 3) for i in range(n + 1)]


def probe(points: list[tuple[float, float, float]]) -> dict:
    body = {"ue_positions": [
        {"id": f"probe{i}", "position": list(p), "velocity": [0.0, 0.0, 0.0]}
        for i, p in enumerate(points)]}
    req = urllib.request.Request(
        PHYSICS, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def pick(gains: dict, cell: str) -> float:
    """從 path_gain 取出某個 cell 的線性增益。

    PathSolver 的鍵是 `名稱#PCI`(例:`s07#150`),而劇本與 CU 用的是
    `s07_c0`。這個落差先前也讓 UE 的重選網挑錯 cell —— 同一個坑第二次,
    所以這裡直接吃三種寫法:s07 / s07_c0 / s07#150。
    """
    want = cell.split("#")[0].removesuffix("_c0")
    for k, v in gains.items():
        if k.split("#")[0].removesuffix("_c0") == want:
            return v
    return 0.0


def db(linear: float) -> float:
    return 10.0 * math.log10(linear) if linear and linear > 0 else float("-inf")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serving", required=True, help="UE 現在該駐留的 cell")
    ap.add_argument("--target", required=True, help="希望它換過去的 cell")
    ap.add_argument("--x", required=True, help="掃描範圍 起:迄:步長")
    ap.add_argument("--y", default="0")
    ap.add_argument("--z", default="1.5")
    ap.add_argument("--window", default="1.5:4.5",
                    help="可用增益區間 下限:上限(dB);預設是窄窗題的經驗值")
    a = ap.parse_args()

    lo, hi = (float(v) for v in a.window.split(":"))
    pts = [(x, y, z) for x in _rng(a.x) for y in _rng(a.y) for z in _rng(a.z)]
    if len(pts) > 200:
        print(f"候選點 {len(pts)} 個太多,PathSolver 會很慢 —— 請放大步長", file=sys.stderr)
        return 2

    print(f"實測 {len(pts)} 個候選點({a.serving} → {a.target},可用窗 {lo}~{hi} dB)…")
    try:
        res = probe(pts)
    except Exception as exc:                     # noqa: BLE001 — 這是給人看的工具
        print(f"PathSolver 呼叫失敗:{exc}", file=sys.stderr)
        print("→ 失敗時**不要**改用估算,先把 physics 修好。", file=sys.stderr)
        return 2

    gains = (res.get("data") or res).get("path_gain") or {}
    hits = []
    print(f"\n{'位置 (x,y,z)':<26}{a.serving:>12}{a.target:>12}{'增益':>10}   判定")
    print("-" * 74)
    for i, p in enumerate(pts):
        g = gains.get(f"probe{i}") or {}
        s_db, t_db = db(pick(g, a.serving)), db(pick(g, a.target))
        if s_db == float("-inf") or t_db == float("-inf"):
            print(f"{str(p):<26}{'—':>12}{'—':>12}{'—':>10}   量不到(cell 名稱對嗎?)")
            continue
        delta = t_db - s_db
        ok = lo <= delta <= hi
        if ok:
            hits.append((p, delta, s_db))
        print(f"{str(p):<26}{s_db:>12.1f}{t_db:>12.1f}{delta:>+10.1f}   "
              f"{'✅ 落在窗內' if ok else ('太小,不會觸發' if delta < lo else '太大,會直接掉線或不算窄窗')}")

    if not hits:
        print(f"\n❌ 沒有任何位置落在 {lo}~{hi} dB —— **不要憑估算挑一個**。")
        print("   要嘛換掃描範圍,要嘛改場景幾何(移動 cell / 改天線朝向),")
        print("   要嘛調整該劇本的 a3_offset 把窗搬到訊號實際做得到的區間。")
        return 1

    best = min(hits, key=lambda h: abs(h[1] - (lo + hi) / 2))
    print(f"\n✅ {len(hits)} 個位置可用。建議取窗中央:{best[0]} 增益 {best[1]:+.1f} dB"
          f"(服務端 {best[2]:.1f} dB)")
    print("   把這個座標寫進劇本,並在交付前用同一支指令複驗一次。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
