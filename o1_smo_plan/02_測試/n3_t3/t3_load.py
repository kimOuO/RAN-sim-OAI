#!/usr/bin/env python3
"""N3 T3 負載腳本(2026-10-01):對 run 內每個 CU 的 CONNECTED UE 設定 traffic_profile(cbr, rate_mbps),
做出「先低負載、再升高」。每 20 秒重套一次(UE 進出場後 UE driver 會重推劇本提示,需覆蓋回來)。
用法:t3_load.py <rid> <phase_json>
  phase_json 例:'[[0, 0.2], [900, 4.0], [1800, 0.2]]'  → 自腳本啟動起 0 s 用 0.2 Mbps、900 s 起 4.0、1800 s 起回 0.2
CU 容器 cu-<rid>-<n> 的 host port 由 docker port 取得。"""
import json, subprocess, sys, time, urllib.request

rid, phases = sys.argv[1], json.loads(sys.argv[2])
def cu_ports():
    out = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True).stdout.split()
    ports = []
    for n in sorted(x for x in out if x.startswith(f"cu-{rid}-")):
        p = subprocess.run(["docker", "port", n, "8000"], capture_output=True, text=True).stdout.strip().split("\n")[0]
        ports.append((n, p.rsplit(":", 1)[-1]))
    return ports
def post(port, path, body):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/v0.1/CU/{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)
t0 = time.time()
applied = {}
while True:
    el = time.time() - t0
    rate = next((r for t, r in reversed(phases) if el >= t), phases[0][1])
    for name, port in cu_ports():
        try:
            ues = post(port, "Session/SessionController/list", {}).get("data") or []
            for u in ues:
                if u.get("rrc_state") != "CONNECTED":
                    continue
                key = (name, u["ue_id"])
                if applied.get(key) == rate and el - applied.get(("t",) + key, -999) < 60:
                    continue
                post(port, "Session/SessionController/update_traffic_profile",
                     {"ue_id": u["ue_id"], "traffic_profile": {"pattern": "cbr", "rate_mbps": rate, "ul_rate_mbps": rate / 8.0}})
                applied[key] = rate
                applied[("t",) + key] = el
        except Exception as exc:  # noqa: BLE001
            print(time.strftime("%H:%M:%S"), name, "err", exc, flush=True)
    print(time.strftime("%H:%M:%S"), f"t={int(el)}s rate={rate} Mbps", flush=True)
    if el > phases[-1][0] + 3600:
        break
    time.sleep(20)
