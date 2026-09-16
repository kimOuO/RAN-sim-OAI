"""實驗 C-2:corridor 場景只存前 K 條路徑,重建的 H 會差多少。

用法(physics 容器內):
  SCENARIO_STORE_URL=http://scene-management-backend:8000 python3 /app/precompute/experiment_c_topk.py /tmp/path_synth.py corridor_24h 60000
第三個參數是取樣的 tick(UE 要在場)。用 8×8 cross(32T)當 gNB、1×2 cross 當 UE。
"""
import importlib.util
import os
import sys

sys.argv, (synth_path, sid, tick) = sys.argv[:1], sys.argv[1:4]
sys.path.insert(0, "/app/precompute")
import run_precompute as rp  # noqa: E402  (會 django.setup)
import numpy as np  # noqa: E402

spec = importlib.util.spec_from_file_location("path_synth", synth_path)
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)
S = rp.SionnaBusinessService

sc = rp._fetch_scenario(sid)
raw = sc.get("raw_json") or {}
S.reload_scene_config()
S.apply_override({"scene_id": raw.get("scene_id") or sid, "override_mode": "full",
                  "geometry_source": raw.get("geometry_source") or {"type": "buildings_json", "buildings": raw.get("buildings") or []},
                  "gnbs": raw.get("gnbs")})
meta = S.enable_path_params()
t_sec = int(tick) * int(raw.get("tick_ms", 500)) / 1000.0
ues = [{"id": u["name"], "position": [float(v) for v in rp._interpolate_position(u["positions"], t_sec)]} for u in raw["ues"]]
res = S.compute_path_params(ue_positions=ues, top_k=400)

TX = dict(rows=8, cols=8, polarization="cross")
RX = dict(rows=1, cols=2, polarization="cross")
rows = []
for ue, per in res["paths"].items():
    for tx, (A, kt, kr) in per.items():
        p = np.sum(np.abs(A) ** 2, axis=(1, 2))
        n = int(np.sum(p > 0))
        if n == 0:
            continue
        H = ps.synthesize(A, kt, kr, tx=TX, rx=RX, tx_orientation=meta["orientation"][tx], fading=False)
        out = [ue, tx, n]
        for k in (4, 6, 8, 12, 24):
            Hk = ps.synthesize(A[:k], kt[:k], kr[:k], tx=TX, rx=RX, tx_orientation=meta["orientation"][tx], fading=False)
            out.append((p[:k].sum() / p.sum(), np.linalg.norm(Hk - H) / np.linalg.norm(H)))
        rows.append(out)
print(f"tick {tick}:{len(rows)} 組 (UE, cell) 有路徑")
for k_i, k in enumerate((4, 6, 8, 12, 24)):
    cap = np.array([r[3 + k_i][0] for r in rows]); err = np.array([r[3 + k_i][1] for r in rows])
    print(f"K={k:>2}: 捕捉功率 中位 {np.median(cap)*100:.1f}% 最差 {cap.min()*100:.1f}% | H 相對誤差 中位 {np.median(err):.3f} 90% {np.quantile(err, .9):.3f} 最差 {err.max():.3f}")
print("路徑數 中位", int(np.median([r[2] for r in rows])), "最多", max(r[2] for r in rows))
