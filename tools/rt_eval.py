#!/usr/bin/env python3
"""射線追蹤快取評估:穩定度 + 對 TR 38.901 InH 的絕對值比對。
用法(在有 numpy 的容器內跑): rt_eval.py <npz> <geometry.json>

穩定度:NaN 比例、相鄰 tick |Δ| 的 p50/p95/p99.9/max。
準確度:把每格的 path gain 對 TR 38.901 Table 7.4.1-1 的 InH-Office 模型比。
  LOS : PL = 32.4 + 17.3 log10(d3D) + 20   log10(fc_GHz)     σ=3.02
  NLOS: PL = 38.3 log10(d3D) + 17.30 + 24.9 log10(fc_GHz)     σ=7.92
        (TR 38.901 取 max(PL_LOS, PL_NLOS))
我們不知道每格是 LOS 還 NLOS,所以兩條都列,看實測落在哪裡、斜率對不對。
"""
import sys, json
import numpy as np

npz, geo_path = sys.argv[1], sys.argv[2]
z = np.load(npz, allow_pickle=True)
g = z["path_gain_db"]                      # [tick, ue, cell]
ue_names = [str(x) for x in z["ue_names"]]
cell_names = [str(x) for x in z["cell_names"]]
geo = json.load(open(geo_path))            # {"cells": {name:[x,y,z]}, "ue_tracks": {ue:[[t,x,y,z],...]}}
tick_ms = int(z["tick_ms"])

print("== 穩定度 ==")
nan = np.isnan(g); v = g[~nan]
d = np.abs(np.diff(g, axis=0)); d = d[~np.isnan(d)]
print("NaN %.2f%%   有值 min %.0f p01 %.0f p50 %.0f max %.0f" %
      (100*nan.mean(), v.min(), np.percentile(v,1), np.median(v), v.max()))
print("相鄰 tick |Δ| dB: p50 %.2f  p95 %.2f  p99.9 %.1f  max %.1f" %
      (np.median(d), np.percentile(d,95), np.percentile(d,99.9), d.max()))

print("== 對 TR 38.901 ==")
fc = float(geo.get("fc_ghz", 3.5))
model = geo.get("model", "UMa")        # UMa(室外高站)或 InH(室內)
rows = []
for ci, cname in enumerate(cell_names):
    base = cname.split("#")[0]
    cpos = geo["cells"].get(cname) or geo["cells"].get(base)
    if cpos is None:
        continue
    cpos = np.asarray(cpos, dtype=float)
    for ui, uname in enumerate(ue_names):
        tr = geo["ue_tracks"].get(uname)
        if not tr:
            continue
        tr = np.asarray(tr, dtype=float)
        for k in range(g.shape[0]):
            val = g[k, ui, ci]
            if np.isnan(val):
                continue
            t = k * tick_ms / 1000.0
            p = np.array([np.interp(t, tr[:, 0], tr[:, j]) for j in (1, 2, 3)])
            d3 = float(np.linalg.norm(p - cpos))
            d2 = float(np.hypot(p[0] - cpos[0], p[2] - cpos[2]))
            if d3 < 1.0:
                continue
            rows.append((d3, d2, p[1], cpos[1], -float(val)))
if not rows:
    print("  (無幾何資料可比)"); raise SystemExit
a = np.array(rows)
d3, d2, hut, hbs, pl = a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4]

if model == "InH":
    # TR 38.901 Table 7.4.1-1 InH-Office
    los = 32.4 + 17.3 * np.log10(d3) + 20.0 * np.log10(fc)
    nlos = np.maximum(los, 38.3 * np.log10(d3) + 17.30 + 24.9 * np.log10(fc))
    n_los, n_nlos = 1.73, 3.83
else:
    # TR 38.901 Table 7.4.1-1 UMa(hBS 名義 25 m、hUT 1.5–22.5 m)
    he = 1.0
    d_bp = 4.0 * (hbs - he) * (hut - he) * fc * 1e9 / 3e8
    pl1 = 28.0 + 22.0 * np.log10(d3) + 20.0 * np.log10(fc)
    pl2 = (28.0 + 40.0 * np.log10(d3) + 20.0 * np.log10(fc)
           - 9.0 * np.log10(d_bp ** 2 + (hbs - hut) ** 2))
    los = np.where(d2 <= d_bp, pl1, pl2)
    nlos = np.maximum(los, 13.54 + 39.08 * np.log10(d3) + 20.0 * np.log10(fc)
                      - 0.6 * (hut - 1.5))
    n_los, n_nlos = 2.2, 3.91

print("  模型 %s,樣本 %d,3D 距離 %.1f–%.1f m,fc %.2f GHz,hBS %.1f m" %
      (model, len(d3), d3.min(), d3.max(), fc, hbs[0]))
for name, ref in (("LOS", los), ("NLOS", nlos)):
    r = pl - ref
    print("  實測 − %-4s : 中位 %+7.1f dB  p05 %+7.1f  p95 %+7.1f" %
          (name, np.median(r), np.percentile(r, 5), np.percentile(r, 95)))
A = np.vstack([10 * np.log10(d3), np.ones_like(d3)]).T
n_fit, c_fit = np.linalg.lstsq(A, pl, rcond=None)[0]
print("  實測路徑損耗指數 n = %.2f(%s LOS %.2f / NLOS %.2f);截距 %.1f dB"
      % (n_fit, model, n_los, n_nlos, c_fit))
print("  註:38.901 是跨站點的統計平均,site-specific 光追本來就會偏離;"
      "看的是量級是否合理、斜率是否在 LOS–NLOS 之間,不是要求吻合。")
