"""從一個 24h 走廊母場景切出時窗切片:registry 的場景資料 + 通道快取一起切。

既有的 precompute/carve_window.py 只切快取,而且來源寫死 corridor_24h;
場景那一半(waypoints / 流量 / 在場時段)以前是靠劇本 JSON 重新匯入。
這支把兩邊一起做,來源與目標都可指定。

用法:
    python3 tools/carve_corridor_slice.py <母場景名> <切片名> <t0_sec> <t1_sec>

切片的時間軸從 0 開始(全部減去 t0)。三種時間資料的處理:
  waypoints  取窗內的點,並在 t0 / t1 兩端各補一個線性內插的點(避免起點瞬移)
  traffic    取窗內的段,並補上「t0 當下生效的那一段」當開頭
  在場時段    與窗取交集後平移;完全落在窗外的就不建立
"""
from __future__ import annotations

import json
import sys
import urllib.request

REG = "http://localhost:8301/api/v0.1/Scene_management_backend"


def post(path: str, body: dict, timeout: float = 300.0):
    req = urllib.request.Request(f"{REG}/{path}", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    if not d.get("success"):
        raise RuntimeError(f"{path}: {d.get('message')} {d.get('errors')}")
    return d.get("data")


def scene_uuid(name: str) -> str:
    d = post("Field_scene/SceneReader/read", {"name": name})
    row = d[0] if isinstance(d, list) else d
    return row["scene_uuid"]


def lerp(a, b, t):
    """a, b = [t,x,y,z];回傳時間 t 上的線性內插點。"""
    if b[0] == a[0]:
        return list(a)
    f = (t - a[0]) / (b[0] - a[0])
    return [t] + [a[i] + (b[i] - a[i]) * f for i in (1, 2, 3)]


def clip_waypoints(wps, t0, t1):
    wps = sorted(wps, key=lambda w: w[0])
    out = []
    for i, w in enumerate(wps):
        if t0 <= w[0] <= t1:
            if not out and w[0] > t0 and i > 0:      # 窗內第一點之前補內插起點
                out.append(lerp(wps[i - 1], w, t0))
            out.append(list(w))
        elif w[0] > t1:
            if out and out[-1][0] < t1:              # 補內插終點
                out.append(lerp(out[-1], w, t1))
            break
    if not out:                                       # 整段都在兩點之間 → 用內插的頭尾
        prev = [w for w in wps if w[0] <= t0]
        nxt = [w for w in wps if w[0] >= t1]
        if prev and nxt:
            out = [lerp(prev[-1], nxt[0], t0), lerp(prev[-1], nxt[0], t1)]
    return [[round(w[0] - t0, 3)] + [round(v, 3) for v in w[1:]] for w in out]


def clip_schedule(sch, t0, t1):
    """流量排程 [[t, dl, ul], ...]:窗內的段 + t0 當下生效的那一段。"""
    sch = sorted(sch, key=lambda s: s[0])
    cur = None
    out = []
    for s in sch:
        if s[0] <= t0:
            cur = s
        elif s[0] <= t1:
            out.append([round(s[0] - t0, 3), s[1], s[2]])
    if cur is not None:
        out.insert(0, [0.0, cur[1], cur[2]])
    elif not out or out[0][0] > 0:
        out.insert(0, [0.0, 0.0, 0.0])
    return out


def clip_windows(aws, t0, t1):
    out = []
    for a, b in aws or []:
        lo, hi = max(a, t0), min(b, t1)
        if hi > lo:
            out.append([round(lo - t0, 3), round(hi - t0, 3)])
    return out


def main():
    src_name, dst_name, t0, t1 = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
    src = scene_uuid(src_name)
    tree = post("Field_scene/SceneReader/read_full_tree", {"scene_uuid": src})
    print(f"母場景 {src_name}:{len(tree['ues'])} 個 UE")

    dst = post("Field_scene/SceneController/duplicate",
               {"scene_uuid": src, "name": dst_name, "legacy_scenario_id": dst_name})["scene_uuid"]
    print(f"  已複製 → {dst_name}")

    dtree = post("Field_scene/SceneReader/read_full_tree", {"scene_uuid": dst})
    by_name = {u["name"]: u for u in dtree["ues"]}

    for su in tree["ues"]:
        du = by_name.get(su["name"])
        if du is None:
            continue
        wps = clip_waypoints(su.get("waypoints") or [], t0, t1)
        for w in post("Equipment_ue/UeWaypointReader/read", {"f_ue_uuid": du["ue_uuid"]}) or []:
            post("Equipment_ue/UeWaypointController/delete", {"ue_waypoint_uuid": w["ue_waypoint_uuid"]})
        for i, w in enumerate(wps):
            post("Equipment_ue/UeWaypointController/create",
                 {"f_ue_uuid": du["ue_uuid"], "ord": i, "t_sec": w[0], "x": w[1], "y": w[2], "z": w[3]})

        for tr in (du.get("traffic") or []):
            src_tr = (su.get("traffic") or [{}])[0]
            post("Equipment_ue/UeTrafficController/update",
                 {"ue_traffic_uuid": tr["ue_traffic_uuid"],
                  "schedule": clip_schedule(src_tr.get("schedule") or [], t0, t1)})

        for aw in post("Equipment_ue/UeActiveWindowReader/read", {"f_ue_uuid": du["ue_uuid"]}) or []:
            post("Equipment_ue/UeActiveWindowController/delete",
                 {"ue_active_window_uuid": aw["ue_active_window_uuid"]})
        for lo, hi in clip_windows(su.get("active_windows") or [], t0, t1):
            post("Equipment_ue/UeActiveWindowController/create",
                 {"f_ue_uuid": du["ue_uuid"], "t0_sec": lo, "t1_sec": hi})

    # cache_path 一定要填:前端的「啟動」鈕是看 mode=cached 且 cache_path 非空才解鎖,
    # 空的就顯示「先預算」。切片的快取是這支腳本自己切的、沒走 orchestrator 的 precompute,
    # 那條路徑才會回寫這個欄位 —— 不在這裡補,切出來的劇本前端永遠按不動(2026-09-22)。
    post("Simulation_run/SceneRunController/create",
         {"f_scene_uuid": dst, "mode": "cached", "speed_x": 2, "sim_dt_ms": 500,
          "duration_sec": t1 - t0, "status": "ready",
          "cache_path": f"/app/data/channel_cache/{dst_name}.npz"})
    print(f"  場景資料切好({t0:.0f}–{t1:.0f} s → 0–{t1-t0:.0f} s),run 設定已建(ready)")


main()
