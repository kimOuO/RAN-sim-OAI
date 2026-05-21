"""實驗 A — Sionna path_gain vs free-space theoretical(driven by sionna_engine).

設定:
  gNB  at (0, 30, 0)    [我們場景的 x, y_height, z_horizontal]
  UE   at (0, 1.5, 60)
  3D 距離 ≈ 66.4 m
  @ 3.5 GHz 自由空間 PL = 20*log10(4π·d/λ) ≈ 79.7 dB
  → 預期 path_gain ≈ -79.7 dB(全向天線)

比對:
  1. iso pattern + azimuth=0  (純 free space)
  2. iso pattern + azimuth=90 (確認 azimuth 對 iso 沒影響,sanity check)
  3. tr38901 pattern + azimuth=0(目前生產設定)
  4. tr38901 pattern + azimuth=90
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings.local")
import django
django.setup()

from main.apps.ran_signal.services.optional.ran_calculation.sionna_engine import SionnaEngine


GNB_POS = [0.0, 30.0, 0.0]
UE_POS = [0.0, 1.5, 60.0]
FREQ_GHZ = 3.5

dx = UE_POS[0] - GNB_POS[0]
dy = UE_POS[1] - GNB_POS[1]
dz = UE_POS[2] - GNB_POS[2]
d_3d = math.sqrt(dx*dx + dy*dy + dz*dz)
lam = 3e8 / (FREQ_GHZ * 1e9)
fspl_db = 20 * math.log10(4 * math.pi * d_3d / lam)

print(f"=== Geometry ===")
print(f"gNB  pos: {GNB_POS}")
print(f"UE   pos: {UE_POS}")
print(f"3D distance: {d_3d:.2f} m")
print(f"Frequency: {FREQ_GHZ} GHz (λ={lam*100:.2f} cm)")
print(f"Free space PL: {fspl_db:.2f} dB → expected path_gain ≈ {-fspl_db:.2f} dB")
print()


def run_case(pattern: str, azimuth_deg: float, scene_path: str | None = None):
    """跑一個 case,回傳 path_gain_db"""
    scene = scene_path or "/app/scenes/umi_3sector.xml"

    engine = SionnaEngine(
        mitsuba_scene_path=scene,
        gnbs=[{
            "name": "g_test",
            "position": GNB_POS,
            "frequency_ghz": FREQ_GHZ,
            "cells": [{"pci": 0, "azimuth_deg": azimuth_deg, "cell_id": "g_test_c0"}],
        }],
        gnb_antenna_pattern=pattern,
        ue_antenna_pattern=pattern,
        gnb_array_rows=1, gnb_array_cols=1,  # 單天線元素,避免 array gain 混進來
        ue_array_rows=1, ue_array_cols=1,
    )
    result = engine.compute_paths(ue_positions=[{"id": "ue_test", "position": UE_POS}])
    # 抽 path_gain — 真實結構:result['path_gain_linear']['ue_test']['g_test#0']
    pg_dict = (result.get("path_gain_linear") or {}).get("ue_test") or {}
    pg_linear = pg_dict.get("g_test#0") or pg_dict.get("g_test")
    if pg_linear is None or pg_linear <= 0:
        return None
    return 10 * math.log10(float(pg_linear))


cases = [
    ("iso",      0,   "純 free space:isotropic antenna,azimuth 對它沒影響"),
    ("iso",      90,  "isotropic 旋 90°(該跟前面一樣)"),
    ("tr38901",  0,   "生產設定:tr38901 sector + azimuth=0"),
    ("tr38901",  90,  "tr38901 + azimuth=90°(轉向 UE 看效果)"),
    ("dipole",   0,   "dipole,azimuth=0"),
]

print(f"=== Results ===")
print(f"{'Pattern':<10} {'Azimuth':>8}  | {'path_gain_dB':>14} | {'vs free space':>14}")
print(f"{'-'*60}")
for pattern, az, note in cases:
    try:
        pg_db = run_case(pattern, az)
        if pg_db is None:
            print(f"{pattern:<10} {az:>8}°  | {'(no path)':>14} | --")
            continue
        delta = pg_db - (-fspl_db)
        print(f"{pattern:<10} {az:>8}°  | {pg_db:>14.2f} | {delta:>+12.2f} dB  — {note}")
    except Exception as e:
        print(f"{pattern:<10} {az:>8}°  | ERROR: {e}")

print()
print(f"=== 解讀 ===")
print(f"iso(全向)+ free space 應該接近 {-fspl_db:.1f} dB(±2 dB tolerance,Sionna RT 多 path 累加可能略強)")
print(f"如果 iso 已經比 -{fspl_db:.0f} dB 低 10+ dB,代表 Sionna 算 propagation 本身就出問題(scene material 太吸收?)")
print(f"如果 iso 接近 -{fspl_db:.0f} dB,但 tr38901 差很多,代表 antenna pattern + azimuth 對齊有問題")
