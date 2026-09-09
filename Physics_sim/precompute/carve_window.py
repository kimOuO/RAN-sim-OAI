"""從 corridor_24h 的結果切出某個時窗的 channel cache。

24h 的陣列是 [tick, ue, cell],tick 均勻(每 500ms),所以某個時窗就是連續的
一段 slice —— 位置與 UE 順序都跟切片劇本一致,不需要重算。

來源優先用 checkpoint;24h 跑完後 checkpoint 會被刪掉,改讀最終的 .npz。

用法: python3 carve.py <scenario_id> <t0_sec> <t1_sec>
"""
import json, os, sys, urllib.request
import numpy as np

CACHE = "/app/data/channel_cache"
TICK_MS = 500
OMNIVERSE_URL = os.environ.get("OMNIVERSE_URL", "http://omniver_backend:8000")

sid, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
i0, i1 = int(t0 * 1000 / TICK_MS), int(t1 * 1000 / TICK_MS)

ckpt, final = f"{CACHE}/corridor_24h.ckpt.npz", f"{CACHE}/corridor_24h.npz"
src = ckpt if os.path.exists(ckpt) else final
if not os.path.exists(src):
    print("找不到 24h 的結果或 checkpoint"); sys.exit(2)
d = np.load(src, allow_pickle=False)
a = d["path_gain_db"]
done = int(d["next_tick"]) if "next_tick" in d.files else a.shape[0]
print(f"來源 {os.path.basename(src)}  已算到 tick {done}")
if i1 > done:
    print(f"還沒算到 tick {i1} —— 這段不能切"); sys.exit(2)

seg = a[i0:i1]
# NaN 不等於「沒算」—— cache 只在 path_gain > 0 時填值,完全被牆擋住、
# 沒有任何射線抵達的 (tick, ue, cell) 本來就留白(= 無限衰減)。
# 真正代表「沒算」的是**整個 tick 全空**,因為每次呼叫至少會有一個 cell 有值。
allnan = np.isnan(seg).all(axis=(1, 2))
print(f"{sid}: ticks {i0}..{i1} shape={seg.shape} "
      f"未計算的 tick={int(allnan.sum())} 無路徑比例={np.isnan(seg).mean()*100:.1f}%")
if allnan.any():
    print("有整個 tick 沒算到,不能當成完整 cache"); sys.exit(3)

sc = json.load(open(f"/tmp/{sid}.json"))
out = f"{CACHE}/{sid}.npz"
np.savez_compressed(out, path_gain_db=seg,
                    ue_names=np.array([u["name"] for u in sc["ues"]]),
                    cell_names=d["cell_names"],
                    tick_ms=np.int32(TICK_MS),
                    duration_sec=np.float32(t1 - t0),
                    total_ticks=np.int32(i1 - i0))
size = os.path.getsize(out)
v = seg[~np.isnan(seg)]
print(f"寫出 {out}  {size/1e6:.1f} MB  值域 {v.min():.1f} ~ {v.max():.1f} dB")

body = json.dumps({"scenario_id": sid, "precompute_status": "ready",
                   "precompute_progress": 100.0,
                   "cache_path": out, "cache_size_bytes": size}).encode()
req = urllib.request.Request(
    f"{OMNIVERSE_URL.rstrip('/')}/api/v0.1/RAN/Scenario/ScenarioController/update_status",
    data=body, headers={"Content-Type": "application/json"})
print("狀態回寫:", json.load(urllib.request.urlopen(req, timeout=60)).get("success"))
