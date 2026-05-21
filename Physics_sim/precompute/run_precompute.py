#!/usr/bin/env python3
"""Phase B B.2 — Sionna 離線預算 worker (CLI script,跑在 physics container 內)。

Usage:
    docker exec ransim-physics python /app/precompute/run_precompute.py <scenario_id>

流程:
    1. HTTP GET scenario JSON from Omniverse backend
    2. 對每個 tick × UE,內插出位置
    3. 一個 tick 全 UE 一起餵 SionnaBusinessService.compute_paths (in-process,免 HTTP)
    4. 收 path_gain (per gnb#pci → per UE)
    5. 累積到 numpy 3D 陣列,存 .npz 到 /app/data/channel_cache/{scenario_id}.npz
    6. 階段性 PATCH Omniverse 更新 precompute_status / progress

設計取捨:
- in-process Sionna 比 HTTP 快 100x+,且能直接拿 channel_matrix(MVP 暫只存 path_gain)
- 用 .npz 不用 parquet (physics container 沒 pyarrow,不想為這加 dep)
- single-process,沒平行化(後續可加 multiprocessing)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import requests

# Django setup
sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings.local")
import django  # noqa: E402

django.setup()

from main.apps.ran_signal.services.business.sionna_operations import (  # noqa: E402
    SionnaBusinessService,
)


OMNIVERSE_URL = os.environ.get("OMNIVERSE_URL", "http://omniver_backend:8000")
CACHE_DIR = Path("/app/data/channel_cache")
PROGRESS_UPDATE_EVERY = 50  # tick


def _fetch_scenario(scenario_id: str) -> dict:
    r = requests.post(
        f"{OMNIVERSE_URL}/api/v0.1/RAN/Scenario/ScenarioController/read",
        json={"scenario_id": scenario_id},
        timeout=10,
    )
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(f"Omniverse read failed: {body}")
    return body["data"]


def _patch_status(scenario_id: str, **fields):
    """呼 Omniverse Scenario/update_status,把 precompute 進度 / 結果寫回 DB。"""
    payload = {"scenario_id": scenario_id, **fields}
    try:
        r = requests.post(
            f"{OMNIVERSE_URL}/api/v0.1/RAN/Scenario/ScenarioController/update_status",
            json=payload,
            timeout=5,
        )
        if not r.ok:
            print(f"[STATUS WARN] HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[STATUS WARN] {e}")


def _interpolate_position(
    positions: list[list[float]], t_sec: float
) -> tuple[float, float, float]:
    """positions = [[t, x, y, z], ...] sorted by t. 線性內插。t 超出範圍 clamp."""
    if not positions:
        return (0.0, 0.0, 0.0)
    if t_sec <= positions[0][0]:
        p = positions[0]
        return (p[1], p[2], p[3])
    if t_sec >= positions[-1][0]:
        p = positions[-1]
        return (p[1], p[2], p[3])
    # 二分法找區間
    for i in range(len(positions) - 1):
        if positions[i][0] <= t_sec <= positions[i + 1][0]:
            t0, x0, y0, z0 = positions[i]
            t1, x1, y1, z1 = positions[i + 1]
            if t1 == t0:
                return (x0, y0, z0)
            r = (t_sec - t0) / (t1 - t0)
            return (
                x0 + (x1 - x0) * r,
                y0 + (y1 - y0) * r,
                z0 + (z1 - z0) * r,
            )
    return (positions[-1][1], positions[-1][2], positions[-1][3])


def run(scenario_id: str) -> int:
    print(f"[precompute] start scenario_id={scenario_id}")
    _patch_status(scenario_id, precompute_status="running", precompute_progress=0.0, precompute_error="")

    # 1. 取 scenario
    try:
        sc = _fetch_scenario(scenario_id)
    except Exception as e:
        _patch_status(scenario_id, precompute_status="failed", precompute_error=f"fetch: {e}")
        print(f"[precompute] ERROR fetch scenario: {e}", file=sys.stderr)
        return 2

    raw = sc.get("raw_json") or {}
    duration_sec = float(raw.get("duration_sec", 0))
    tick_ms = int(raw.get("tick_ms", 500))
    ues = raw.get("ues", [])
    if not ues or duration_sec <= 0:
        _patch_status(scenario_id, precompute_status="failed", precompute_error="empty ues or zero duration")
        print("[precompute] ERROR empty ues or zero duration", file=sys.stderr)
        return 3

    total_ticks = int(duration_sec * 1000 // tick_ms)
    ue_names = [u["name"] for u in ues]
    print(
        f"[precompute] total_ticks={total_ticks} ues={len(ue_names)} tick_ms={tick_ms}"
    )

    # 2. 確保 Sionna engine 啟動(讀 scene_config.json)
    print("[precompute] loading Sionna scene...")
    SionnaBusinessService.reload_scene_config()
    print("[precompute] Sionna ready")

    # 3. 預備儲存結構 — gnb_cell_names 在第一個 tick 後才知道,先空著
    cell_names: list[str] | None = None
    # cache_3d[tick_idx, ue_idx, cell_idx] = path_gain_linear (after sionna)
    cache_3d: np.ndarray | None = None

    t_start = time.perf_counter()
    progress_t_last = t_start

    # Stationary UE optimization:UE 位置在 tolerance 內沒變 → reuse 上個 tick 的
    # path_gain,不打 Sionna。對 full_day_24hr 這類 stationary scenario 從 ~5 hr
    # GPU 降到秒級。moving UE 場景每 tick 位置都不同,filter 永遠 miss,行為不變。
    _POS_TOLERANCE_M = 0.01    # 1 cm 內視為「沒動」
    last_positions: list[tuple[float, float, float] | None] = [None] * len(ues)
    last_path_gain: dict | None = None
    sionna_call_count = 0

    for tick_idx in range(total_ticks):
        t_sec = tick_idx * tick_ms / 1000.0

        # 內插 UE 位置 + 檢查是否所有 UE 都沒動
        ue_positions = []
        all_stationary = True
        for ue_idx, ue in enumerate(ues):
            pos = _interpolate_position(ue["positions"], t_sec)
            ue_positions.append({
                "id": ue["name"],
                "position": [float(pos[0]), float(pos[1]), float(pos[2])],
                "velocity": [0.0, 0.0, 0.0],
            })
            lp = last_positions[ue_idx]
            if lp is None:
                all_stationary = False
            else:
                if (abs(pos[0]-lp[0]) > _POS_TOLERANCE_M
                        or abs(pos[1]-lp[1]) > _POS_TOLERANCE_M
                        or abs(pos[2]-lp[2]) > _POS_TOLERANCE_M):
                    all_stationary = False
            last_positions[ue_idx] = (float(pos[0]), float(pos[1]), float(pos[2]))

        # Stationary fast-path:全部 UE 都沒動 → 複用上次 path_gain
        if all_stationary and last_path_gain is not None:
            result = {"path_gain_linear": last_path_gain}
        else:
            try:
                result = SionnaBusinessService.compute_paths(ue_positions=ue_positions)
                sionna_call_count += 1
            except Exception as e:
                _patch_status(scenario_id, precompute_status="failed", precompute_error=f"tick {tick_idx}: {e}")
                print(f"[precompute] ERROR tick={tick_idx} compute_paths: {e}", file=sys.stderr)
                return 4
            last_path_gain = result.get("path_gain_linear") or result.get("path_gain") or {}

        # 結構:path_gain_linear[ue_name][cell_name] = float (linear)
        # 例: {"ue_demo_a": {"gnb4#0": 1.2e-9, "gnb4#1": 3.4e-10, ...}, ...}
        path_gain_linear = result.get("path_gain_linear") or result.get("path_gain") or {}

        # 第一個 tick 才知道 cell 集合,初始化 3D 陣列
        if cell_names is None:
            cells_set: set[str] = set()
            for per_ue in path_gain_linear.values():
                if isinstance(per_ue, dict):
                    cells_set.update(per_ue.keys())
            cell_names = sorted(cells_set)
            cache_3d = np.full(
                (total_ticks, len(ue_names), len(cell_names)),
                fill_value=np.nan, dtype=np.float32,
            )
            print(f"[precompute] cells={len(cell_names)}: {cell_names}")

        # 填值:cache[tick, ue, cell] = 10 log10(path_gain_linear)
        for ue_idx, ue_name in enumerate(ue_names):
            per_ue = path_gain_linear.get(ue_name) or {}
            if not isinstance(per_ue, dict):
                continue
            for cell_idx, cell_name in enumerate(cell_names):
                g = per_ue.get(cell_name)
                if g and g > 0:
                    cache_3d[tick_idx, ue_idx, cell_idx] = 10.0 * np.log10(g)

        # 進度更新
        if (tick_idx + 1) % PROGRESS_UPDATE_EVERY == 0:
            now = time.perf_counter()
            rate = PROGRESS_UPDATE_EVERY / (now - progress_t_last)
            progress_t_last = now
            pct = (tick_idx + 1) / total_ticks * 100
            eta_sec = (total_ticks - tick_idx - 1) / max(rate, 0.1)
            print(
                f"[precompute] {tick_idx + 1}/{total_ticks} ({pct:.1f}%) "
                f"rate={rate:.1f} t/s ETA={eta_sec:.0f}s"
            )
            _patch_status(scenario_id, precompute_progress=pct)

    # 4. 寫 npz
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CACHE_DIR / f"{scenario_id}.npz"
    np.savez_compressed(
        str(out_path),
        path_gain_db=cache_3d,
        ue_names=np.array(ue_names),
        cell_names=np.array(cell_names or []),
        tick_ms=np.int32(tick_ms),
        duration_sec=np.float32(duration_sec),
        total_ticks=np.int32(total_ticks),
    )
    size_bytes = out_path.stat().st_size

    elapsed = time.perf_counter() - t_start
    print(
        f"[precompute] stationary optimization:Sionna calls {sionna_call_count}/{total_ticks} "
        f"({sionna_call_count/total_ticks*100:.1f}% of ticks)"
    )
    print(
        f"[precompute] DONE {scenario_id}: {total_ticks} ticks × "
        f"{len(ue_names)} UEs × {len(cell_names or [])} cells in {elapsed:.1f}s; "
        f"cache={out_path} size={size_bytes}B"
    )

    # 5. 通知 Omniverse
    _patch_status(
        scenario_id,
        precompute_status="ready",
        precompute_progress=100.0,
        cache_path=str(out_path),
        cache_size_bytes=int(size_bytes),
    )
    print(f"[precompute] cache_path={out_path} status=ready")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sionna offline precompute worker")
    parser.add_argument("scenario_id", help="scenario_id from Omniverse Scenario API")
    args = parser.parse_args()
    sys.exit(run(args.scenario_id))
