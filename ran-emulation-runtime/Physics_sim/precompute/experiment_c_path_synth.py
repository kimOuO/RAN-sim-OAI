"""實驗 C:1×1 VH 路徑參數重建的 H,是否等於 Sionna 直接用整個陣列算的 H。

用法(physics 容器內):python3 /app/precompute/experiment_c_path_synth.py /tmp/path_synth.py
第一個參數是 RU 的 path_synth.py(docker cp 進來)。不開 fast fading,取全部路徑,兩邊應只差數值誤差。
"""
import importlib.util
import math
import sys

import numpy as np
import sionna.rt as rt

spec = importlib.util.spec_from_file_location("path_synth", sys.argv[1])
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)

CASES = [
    # (tx 設定, rx 設定, tx orientation)
    (dict(rows=4, cols=4, polarization="cross", vertical_spacing=0.5, horizontal_spacing=0.5), dict(rows=1, cols=2, polarization="cross"), (0.6, 0.2, 0.0)),
    (dict(rows=2, cols=8, polarization="V", vertical_spacing=0.7, horizontal_spacing=0.5), dict(rows=1, cols=1, polarization="V"), (-1.1, 0.35, 0.1)),
    (dict(rows=8, cols=2, polarization="VH", vertical_spacing=0.8, horizontal_spacing=0.5), dict(rows=2, cols=1, polarization="VH"), (2.0, -0.2, 0.0)),
]
RX_POS = [[40.0, 5.0, 1.5], [-30.0, 20.0, 1.5], [10.0, -35.0, 1.5]]
GNB_PAT, UE_PAT = "tr38901", "iso"


def run(tx_arr, rx_arr, orient):
    scene = rt.load_scene(rt.scene.simple_street_canyon)
    scene.frequency = 3.5e9
    scene.tx_array = tx_arr
    scene.rx_array = rx_arr
    scene.add(rt.Transmitter(name="tx", position=[0.0, 0.0, 20.0], orientation=list(orient)))
    for i, p in enumerate(RX_POS):
        scene.add(rt.Receiver(name=f"rx{i}", position=p))
    paths = rt.PathSolver()(scene=scene, max_depth=3, los=True, specular_reflection=True,
                            diffuse_reflection=False, refraction=True, diffraction=False)
    return scene, paths


def planar(cfg, pattern):
    return rt.PlanarArray(num_rows=cfg["rows"], num_cols=cfg["cols"],
                          vertical_spacing=cfg.get("vertical_spacing", 0.5),
                          horizontal_spacing=cfg.get("horizontal_spacing", 0.5),
                          pattern=pattern, polarization=cfg["polarization"])


worst = 0.0
for tx_cfg, rx_cfg, orient in CASES:
    _, p_full = run(planar(tx_cfg, GNB_PAT), planar(rx_cfg, UE_PAT), orient)
    ar, ai = p_full.a
    a_full = (np.array(ar) + 1j * np.array(ai))           # [rx, rx_ant, tx, tx_ant, P]
    H_full = a_full[..., 0, :].sum(axis=-1) if a_full.ndim == 6 else a_full.sum(axis=-1)

    scene, p_vh = run(rt.PlanarArray(num_rows=1, num_cols=1, pattern=GNB_PAT, polarization="VH"),
                      rt.PlanarArray(num_rows=1, num_cols=1, pattern=UE_PAT, polarization="VH"), orient)
    br, bi = p_vh.a
    a = (np.array(br) + 1j * np.array(bi)) * np.array(p_vh.valid)[:, None, :, None, :]
    th_t, ph_t = np.array(p_vh.theta_t), np.array(p_vh.phi_t)
    th_r, ph_r = np.array(p_vh.theta_r), np.array(p_vh.phi_r)
    k = lambda th, ph: np.stack([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)], -1)
    kt, kr = k(th_t, ph_t), k(th_r, ph_r)
    for i in range(len(RX_POS)):
        A = np.transpose(a[i, :, 0, :, :], (2, 0, 1))        # (P, 2, 2)
        H_syn = ps.synthesize(A, kt[i, 0], kr[i, 0], tx=tx_cfg, rx=rx_cfg, tx_orientation=orient, fading=False)
        Hf = H_full[i, :, 0, :]
        err = np.linalg.norm(H_syn - Hf) / max(np.linalg.norm(Hf), 1e-30)
        worst = max(worst, err)
        print(f"tx={tx_cfg['rows']}x{tx_cfg['cols']}/{tx_cfg['polarization']} rx={rx_cfg['rows']}x{rx_cfg['cols']}/{rx_cfg['polarization']} "
              f"ue{i}: shape full={Hf.shape} syn={H_syn.shape} |H|²={np.linalg.norm(Hf)**2:.3e} 相對誤差={err:.2e}")
print(f"最大相對誤差 {worst:.2e} → {'PASS' if worst < 1e-3 else 'FAIL'}")
