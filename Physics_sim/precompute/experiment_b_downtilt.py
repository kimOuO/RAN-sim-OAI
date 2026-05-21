"""實驗 B — 試不同 downtilt 角度,看 path_gain 改善多少。

幾何:gNB(0,30,0)+ UE(0,1.5,60)+ tr38901 sector + azimuth=0
elevation angle = atan(28.5/60) = -25.4°(UE 在天線下方 25.4°)

Sionna orientation 是 [alpha, beta, gamma] ZYX rotation。
alpha = azimuth(繞 z),beta = elevation(繞 y),gamma = roll(繞 x)。
試正負兩種 beta 找對的方向。
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings.local")
import django
django.setup()

import sionna.rt as rt  # noqa: E402


GNB_POS = [0.0, 30.0, 0.0]
UE_POS = [0.0, 1.5, 60.0]
FREQ_GHZ = 3.5

# 自己建一個 minimal scene 不靠 SionnaEngine,直接控 orientation
solver = rt.PathSolver()


def run_case(beta_deg: float):
    scene = rt.load_scene("/app/scenes/umi_3sector.xml")
    scene.frequency = FREQ_GHZ * 1e9

    # 用簡單 1x1 array tr38901 sector
    scene.tx_array = rt.PlanarArray(num_rows=1, num_cols=1, pattern="tr38901", polarization="V")
    scene.rx_array = rt.PlanarArray(num_rows=1, num_cols=1, pattern="iso", polarization="V")

    # azimuth=0,beta = downtilt
    alpha = 0.0
    beta = math.radians(beta_deg)
    gamma = 0.0
    tx = rt.Transmitter(name="g_test", position=GNB_POS, orientation=[alpha, beta, gamma])
    scene.add(tx)
    rx = rt.Receiver(name="ue_test", position=UE_POS)
    scene.add(rx)

    paths = solver(scene=scene, max_depth=5)
    # 從 paths 取 path_gain。Sionna 5 用 cir() 或 .a 直接
    try:
        a, _ = paths.cir(out_type="numpy")
        # a shape: [num_rx, num_rx_ant, num_tx, num_tx_ant, num_paths, num_time_steps]
        # path gain linear = sum |a|^2 across paths
        import numpy as np
        pg_linear = float(np.sum(np.abs(a) ** 2))
        return 10 * math.log10(pg_linear) if pg_linear > 0 else None
    except Exception as e:
        return f"ERROR: {e}"


print(f"=== gNB at {GNB_POS} (height 30m)  UE at {UE_POS} (height 1.5m)")
print(f"=== Geometric elevation = -25.4° (UE below antenna horizon)")
print()
print(f"{'beta_deg':>10}  {'path_gain_dB':>14}  note")
print('-' * 55)
for beta_deg in [-30, -25, -20, -15, -10, -5, 0, +5, +10, +15, +25]:
    try:
        result = run_case(beta_deg)
        if isinstance(result, float):
            note = ""
            if beta_deg == 0:
                note = "← 目前生產設定(no tilt)"
            elif abs(beta_deg + 25) < 1:
                note = "← 對齊 UE elevation,理論最佳"
            print(f"{beta_deg:>+9}°   {result:>+14.2f}  {note}")
        else:
            print(f"{beta_deg:>+9}°   {result}")
    except Exception as e:
        print(f"{beta_deg:>+9}°   FAIL: {e}")
