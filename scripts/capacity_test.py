#!/usr/bin/env python3
"""RAN sim 容量掃描 — 無建築(自由空間)下最大 gNB/UE 支撐量實測。

判準:1x 速度下 achieved_speed_x ≥ 0.95 且 KPM 有效 UE 比例 ≥ 90%。
用法:nohup setsid python3 capacity_test.py > /home/mitlab/capacity_test.log 2>&1 &
"""
import json, subprocess, time, sys

OMNI = "http://localhost:8001/api/v0.1/RAN"
UE_API = "http://localhost:8105/api/v0.1/UE"
CU = "http://localhost:8101/api/v0.1/CU"
DU = "http://localhost:8102/api/v0.1/DU"

def post(url, body=None, timeout=60):
    out = subprocess.run(
        ["curl", "-s", "-X", "POST", url, "-H", "Content-Type: application/json",
         "-d", json.dumps(body or {}), "--max-time", str(timeout)],
        capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except Exception:
        return {}

def docker_cpu():
    out = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{.Name}} {{.CPUPerc}}"],
        capture_output=True, text=True, timeout=20).stdout
    want = {}
    for ln in out.splitlines():
        parts = ln.split()
        if len(parts) == 2 and parts[0] in (
                "ransim-du", "ransim-ru", "ransim-ue", "ransim-physics", "ransim-cu"):
            want[parts[0].replace("ransim-", "")] = parts[1]
    return want

def setup_scene(n_cells, n_ues):
    """清場 → 建 1..n gNB(每 gNB 2 cell)+ n UEs(散布 ±300m,含小軌跡)。"""
    # 移除地圖(無建築)+ 清空既有物件
    post(f"{OMNI}/Map/MapController/detach")
    layout = post(f"{OMNI}/Scene/SceneLayoutReader/read").get("data", {})
    for u in layout.get("ues", []):
        post(f"{OMNI}/UE/UEController/delete", {"name": u["name"]})
    for g in layout.get("gnbs", []):
        post(f"{OMNI}/GNB/GNBController/delete", {"name": g["name"]})

    # gNBs:n_cells 顆 cell,兩兩一組 gNB,格狀擺 300m 間距
    n_gnbs = (n_cells + 1) // 2
    for gi in range(n_gnbs):
        gx = (gi % 3) * 300 - 300
        gz = (gi // 3) * 300 - 150
        cells = []
        for ci in range(min(2, n_cells - gi * 2)):
            cells.append({"pci": gi * 2 + ci, "cell_id": f"g{gi}_c{ci}",
                          "azimuth_deg": ci * 180})
        post(f"{OMNI}/GNB/GNBController/create", {
            "name": f"g{gi}", "position": [gx, 30, gz],
            "frequency_ghz": 3.5, "power_dbm": 30, "bandwidth_mhz": 40,
            "cells": cells})

    # UEs:繞自家最近 gNB 的 100m 方形軌跡
    for ui in range(n_ues):
        gi = ui % n_gnbs
        gx = (gi % 3) * 300 - 300
        gz = (gi // 3) * 300 - 150
        off = 40 + (ui // n_gnbs) * 25
        wps = [[gx - off, 0, gz - off], [gx + off, 0, gz - off],
               [gx + off, 0, gz + off], [gx - off, 0, gz + off]]
        post(f"{OMNI}/UE/UEController/create", {
            "name": f"u{ui:02d}", "position": [wps[0][0], 0, wps[0][2]],
            "waypoints": wps, "speed_mps": 3.0, "loop": True,
            "preset_id": "female_office"})
    return n_gnbs

def measure(tag, n_cells, n_ues, settle_s=45, samples=3):
    t0 = time.time()
    n_gnbs = setup_scene(n_cells, n_ues)
    r = post(f"{UE_API}/Sim/SimController/start",
             {"source": "live_db", "speed_x": 1}, timeout=180)
    print(f"[{tag}] start: {r.get('message')} (setup {time.time()-t0:.0f}s)", flush=True)
    time.sleep(15)
    # 掛流量(每 UE 1 Mbps)
    for ui in range(n_ues):
        post(f"{CU}/Session/SessionController/update_traffic_profile",
             {"ue_id": f"u{ui:02d}",
              "traffic_profile": {"pattern": "cbr", "rate_mbps": 1.0}}, timeout=20)
    time.sleep(settle_s)

    ach, kpm_ok = [], []
    for _ in range(samples):
        d = post(f"{DU}/Tick/TickController/read").get("data", {})
        ach.append(float(d.get("achieved_speed_x") or 0))
        k = post(f"{CU}/E2/E2KpmReporter/read").get("data", {})
        ues = [u for u in k.get("ue_status", []) if u.get("rrc_state") == "CONNECTED"]
        ok = sum(1 for u in ues if u.get("rsrp_dbm") is not None)
        kpm_ok.append((ok, len(ues)))
        time.sleep(10)
    cpu = docker_cpu()
    a = sum(ach) / len(ach)
    ok, tot = kpm_ok[-1]
    verdict = "PASS" if (a >= 0.95 and tot and ok / max(tot, 1) >= 0.9) else "FAIL"
    print(f"[{tag}] cells={n_cells} gnbs={n_gnbs} ues={n_ues} "
          f"achieved={a:.3f} kpm={ok}/{tot} cpu={cpu} => {verdict}", flush=True)
    post(f"{UE_API}/Sim/SimController/stop", timeout=90)
    time.sleep(8)
    return verdict, a

print(f"=== RAN sim 容量掃描(無建築/自由空間, 1x)開始 {time.strftime('%F %T')} ===",
      flush=True)

# Phase A:UE 掃描(固定 2 cell)
for n in [5, 10, 20, 40]:
    v, a = measure(f"UE-{n}", 2, n)
    if v == "FAIL" and a < 0.8:
        print(f"[UE 掃描] 在 {n} UE 明顯跟不上,停止加碼", flush=True)
        break

# Phase B:cell 掃描(固定 10 UE)
for c in [4, 8, 12]:
    v, a = measure(f"CELL-{c}", c, 10)
    if v == "FAIL" and a < 0.8:
        print(f"[cell 掃描] 在 {c} cell 明顯跟不上,停止加碼", flush=True)
        break

post(f"{UE_API}/Sim/SimController/stop", timeout=60)
print(f"=== 掃描結束 {time.strftime('%F %T')} ===", flush=True)
