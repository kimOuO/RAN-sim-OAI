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
import json
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
# 劇本來源:預設 Omniverse;設 SCENARIO_STORE_URL(如 Physics 自己 http://localhost:8000)
# 即可脫離 Omniverse 讀劇本 + 回寫 precompute 狀態。端點形狀相同。
SCENARIO_STORE_URL = os.environ.get("SCENARIO_STORE_URL") or OMNIVERSE_URL
CACHE_DIR = Path("/app/data/channel_cache")
PROGRESS_UPDATE_EVERY = 50  # tick
# 每 N tick 把 DrJit 的快取配置還給 OS。compute_paths 每次都會動 scene.receivers,
# 背後的 DrJit 緩衝不 flush 就只進不出 —— 2026-09-08 跑 corridor_24h 到 46.9%
# (81k tick) 時 RSS 撞到 12 GB 的 mem_limit 被 OOM killer 砍掉,而且速率在
# 撞牆前就從 3.1 t/s 掉到 1.6 t/s(GC 壓力)。engine 本身不重建,所以沒有重載成本。
FLUSH_EVERY = 2000
# 每 N tick 存一次進度。整段 24h 要跑十幾個小時,沒有斷點的話任何中斷都是全部重來。
CHECKPOINT_EVERY = 10000
# 分段結束的離開碼。外層 loop 看到這個就再開一個行程接著跑;0 才是真的做完。
SEGMENT_EXIT_CODE = 75
# 階段 C(2026-09-17):每 (tick, UE, cell) 另存前 K 條路徑的參數到 <scenario>.paths/,
# RU 依天線設定重建元件層 H(cached 模式才有 MIMO / 波束)。0 = 只存 path gain(舊行為)。
PATHS_TOP_K = int(os.environ.get("PRECOMPUTE_PATHS_K", "6"))


class PathSidecar:
    """<scenario>.paths/ 目錄:a.npy (T,U,C,K,2,2) complex64、kt.npy / kr.npy (T,U,C,K,3) float16、meta.json。
    用 memmap 直接寫檔 —— 24h 約 1 GB,不必整包放記憶體;RU 端也用 mmap 讀,多個 RU 共用 page cache。"""

    def __init__(self, scenario_id: str, shape: tuple[int, int, int], k: int, meta: dict, resume: bool):
        import json
        from numpy.lib.format import open_memmap
        self.dir = CACHE_DIR / f"{scenario_id}.paths"
        self.dir.mkdir(parents=True, exist_ok=True)
        T, U, C = shape
        mode = "r+" if resume and (self.dir / "a.npy").exists() else "w+"
        self.a = open_memmap(self.dir / "a.npy", mode=mode, dtype=np.complex64, shape=(T, U, C, k, 2, 2))
        self.kt = open_memmap(self.dir / "kt.npy", mode=mode, dtype=np.float16, shape=(T, U, C, k, 3))
        self.kr = open_memmap(self.dir / "kr.npy", mode=mode, dtype=np.float16, shape=(T, U, C, k, 3))
        prev = {}
        if mode == "r+":   # 續跑:保留上一段寫到哪(否則下一次 checkpoint 前 filled_upto 會消失)
            try:
                prev = json.loads((self.dir / "meta.json").read_text())
            except Exception:  # noqa: BLE001
                prev = {}
        self.meta = {**meta, "top_k": k, "shape": [T, U, C], "complete": False,
                     **({"filled_upto": prev["filled_upto"]} if "filled_upto" in prev else {})}
        self._json = json
        self.write_meta()
        print(f"[precompute] path sidecar {self.dir} mode={mode} K={k}")

    def write_meta(self, **extra) -> None:
        self.meta.update(extra)
        tmp = self.dir / "meta.json.tmp"
        tmp.write_text(self._json.dumps(self.meta, ensure_ascii=False, indent=1))
        tmp.replace(self.dir / "meta.json")

    def put(self, t: int, u: int, c: int, triple) -> None:
        aa, kt, kr = triple
        self.a[t, u, c] = aa
        self.kt[t, u, c] = kt
        self.kr[t, u, c] = kr

    def flush(self) -> None:
        for m in (self.a, self.kt, self.kr):
            m.flush()


def _flush_drjit() -> int:
    """歸還 DrJit 快取,回傳目前 RSS(MB)供監測。"""
    import gc
    gc.collect()
    try:
        import drjit  # type: ignore
        drjit.flush_malloc_cache()
    except Exception:  # noqa: BLE001 — 沒有 drjit 或版本無此 API 就算了
        pass
    try:
        return int(open("/proc/self/status").read()
                   .split("VmRSS:")[1].split()[0]) // 1024
    except Exception:  # noqa: BLE001
        return -1


def _fetch_scenario(scenario_id: str) -> dict:
    r = requests.post(
        f"{SCENARIO_STORE_URL}/api/v0.1/RAN/Scenario/ScenarioController/read",
        json={"scenario_id": scenario_id, **({'scene_run_uuid': os.environ['SCENE_RUN_UUID']} if os.environ.get('SCENE_RUN_UUID') else {})},
        timeout=10,
    )
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(f"Omniverse read failed: {body}")
    return body["data"]


_status_disabled = False


def _patch_status(scenario_id: str, **fields):
    """舊 Omniverse Scenario/update_status 回寫。平台化後 scene_run 狀態由 orchestrator precompute_actor
    依容器結束碼決定;這裡只是相容舊 store,端點 404 一次就永久關閉(2026-09-15,之前每 50 tick 刷一頁 404 HTML)。"""
    global _status_disabled
    if _status_disabled:
        return
    payload = {"scenario_id": scenario_id, **fields}
    try:
        r = requests.post(
            f"{SCENARIO_STORE_URL}/api/v0.1/RAN/Scenario/ScenarioController/update_status",
            json=payload,
            timeout=5,
        )
        if r.status_code == 404:
            _status_disabled = True
            print("[STATUS] update_status 端點不存在(平台化後由 orchestrator 管狀態),之後不再回寫")
        elif not r.ok:
            print(f"[STATUS WARN] HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[STATUS WARN] {e}")


def _interpolate_position(
    positions: list[list[float]], t_sec: float, loop: bool = False
) -> tuple[float, float, float]:
    """positions = [[t, x, y, z], ...] sorted by t. 線性內插。t 超出範圍 clamp.

    loop=True 時 t 超過最後一點就取餘數從頭走,與 UE 端 trajectory 的 "loop" 模式
    (RANsim-UE interp.py:elapsed % total)一致;否則預算的通道會停在終點,與 UE 實際位置對不上。
    """
    if not positions:
        return (0.0, 0.0, 0.0)
    if loop and positions[-1][0] > 0 and t_sec > positions[-1][0]:
        t_sec = t_sec % positions[-1][0]
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


def run(scenario_id: str, resume: bool = False, segment_ticks: int = 0) -> int:
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

    # 2b. per-scenario 幾何/天線覆寫 —— 讓劇本的 gnbs + antenna_pattern 真正進 physics。
    #     reload_scene_config 只讀全域 scene_config,劇本的天線(iso/tr38901)、cell
    #     azimuth、gNB 位置原本都被忽略。用 apply_override(ran_only)只換 gNB/天線、
    #     保留場景 mesh,讓 antenna_pattern + azimuth_deg 可 per-scenario 控制。
    sc_gnbs = raw.get("gnbs")
    sc_antenna = raw.get("antenna_pattern")
    sc_buildings = raw.get("buildings") or []
    # 劇本可以自帶 geometry_source（例如掃描模型的 mitsuba_xml_path）。
    # 沒有的話才退回「用 buildings 方塊建 mesh」的舊行為 —— 對掃描類場景，
    # buildings 是空的，舊行為會把整個幾何清成自由空間，算出來的 channel
    # 完全不是室內（2026-09-08 實際踩到：走廊掃描被換成 0 棟建築的空場景）。
    sc_geometry = raw.get("geometry_source")
    sc_tx, sc_ue = raw.get("tx_antenna"), raw.get("ue_antenna")
    if sc_gnbs or sc_antenna or sc_geometry or sc_tx:
        # geometry_source 用「劇本的 buildings」建 mesh(空 list = 只有地面 = 自由空間)。
        # 原本一律吃全域 umi_3sector.xml(6 棟樓)→ 劇本說無建築卻在都市場景裡算 channel,
        # 造成 cell 被樓遮蔽/翻轉/多徑 variance。改成劇本場景幾何才忠於劇本 + 對齊 OAI AWGN。
        override: dict = {
            "scene_id": raw.get("scene_id") or scenario_id,
            "override_mode": "full",  # 換 mesh(geometry)+ gNB + 天線
            "geometry_source": sc_geometry or {
                "type": "buildings_json",
                "buildings": sc_buildings,
                "ground": raw.get("ground"),  # None → builder 用預設地面
            },
        }
        if sc_gnbs:
            override["gnbs"] = sc_gnbs
        if sc_antenna:
            override["scene_antenna_config"] = {"gnb_antenna_pattern": sc_antenna}
        if sc_tx:   # 與 live(RANsim-UE physics_client.push_scene)同一組欄位
            override["scene_antenna_config"] = {
                "gnb_antenna_pattern": sc_tx.get("pattern", "tr38901"), "gnb_polarization": sc_tx.get("polarization", "V"),
                "gnb_array_rows": sc_tx.get("rows", 1), "gnb_array_cols": sc_tx.get("cols", 1),
                "gnb_v_spacing": sc_tx.get("vertical_spacing", 0.5), "gnb_h_spacing": sc_tx.get("horizontal_spacing", 0.5),
                **({"ue_antenna_pattern": sc_ue.get("pattern", "dipole"), "ue_polarization": sc_ue.get("polarization", "V"),
                    "ue_array_rows": sc_ue.get("rows", 1), "ue_array_cols": sc_ue.get("cols", 1)} if sc_ue else {}),
            }
        try:
            SionnaBusinessService.apply_override(override)
            print(
                f"[precompute] scenario override applied: "
                f"gnbs={len(sc_gnbs or [])} "
                f"geometry={(sc_geometry or {}).get('type') or f'buildings_json({len(sc_buildings)})'} "
                f"antenna_pattern={sc_antenna or '(scene default)'} tx={sc_tx} ue={sc_ue}"
            )
        except Exception as e:
            print(
                f"[precompute] WARN scenario override failed, fall back to scene_config: {e}",
                file=sys.stderr,
            )
    tx_meta = SionnaBusinessService.enable_path_params() if PATHS_TOP_K > 0 else None
    sidecar: PathSidecar | None = None
    last_paths: dict | None = None
    print("[precompute] Sionna ready")

    # 3. 預備儲存結構 — gnb_cell_names 在第一個 tick 後才知道,先空著
    cell_names: list[str] | None = None
    # cache_3d[tick_idx, ue_idx, cell_idx] = path_gain_linear (after sionna)
    cache_3d: np.ndarray | None = None

    t_start = time.perf_counter()
    progress_t_last = t_start

    # 斷點續跑:有 checkpoint 就從上次的 tick 接下去
    ckpt_path = CACHE_DIR / f"{scenario_id}.ckpt.npz"
    resume_from = 0

    # Stationary UE optimization:UE 位置在 tolerance 內沒變 → reuse 上個 tick 的
    # path_gain,不打 Sionna。對 full_day_24hr 這類 stationary scenario 從 ~5 hr
    # GPU 降到秒級。moving UE 場景每 tick 位置都不同,filter 永遠 miss,行為不變。
    _POS_TOLERANCE_M = 0.01    # 1 cm 內視為「沒動」
    last_positions: list[tuple[float, float, float] | None] = [None] * len(ues)
    last_path_gain: dict | None = None
    sionna_call_count = 0

    if resume and ckpt_path.exists():
        try:
            ck = np.load(str(ckpt_path), allow_pickle=False)
            cache_3d = ck["path_gain_db"]
            cell_names = [str(c) for c in ck["cell_names"]]
            resume_from = int(ck["next_tick"])
            print(f"[precompute] resume from tick {resume_from}/{total_ticks} "
                  f"({resume_from / total_ticks * 100:.1f}%)")
        except Exception as e:  # noqa: BLE001 — checkpoint 壞了就從頭跑
            print(f"[precompute] checkpoint 讀取失敗,從頭開始: {e}")
            resume_from = 0

    for tick_idx in range(resume_from, total_ticks):
        t_sec = tick_idx * tick_ms / 1000.0

        # 內插 UE 位置 + 檢查是否所有 UE 都沒動
        ue_positions = []
        all_stationary = True
        for ue_idx, ue in enumerate(ues):
            pos = _interpolate_position(ue["positions"], t_sec, loop=bool(ue.get("loop", False)))
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
            result = {"path_gain_linear": last_path_gain, "paths": last_paths}
        else:
            try:
                if PATHS_TOP_K > 0:
                    result = SionnaBusinessService.compute_path_params(ue_positions=ue_positions, top_k=PATHS_TOP_K)
                    last_paths = result.get("paths")
                else:
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
        if PATHS_TOP_K > 0 and sidecar is None:
            sidecar = PathSidecar(scenario_id, (total_ticks, len(ue_names), len(cell_names)), PATHS_TOP_K,
                                  {"ue_names": ue_names, "cell_names": cell_names, "tick_ms": tick_ms,
                                   "tx_orientation": tx_meta["orientation"], "wavelength_m": tx_meta["wavelength_m"],
                                   "gnb_pattern": tx_meta["gnb_pattern"], "ue_pattern": tx_meta["ue_pattern"],
                                   "frame": "sionna", "a_axes": "[tick, ue, cell, path, rx_pol(V,H), tx_pol(V,H)]"},
                                  resume=resume_from > 0)
        if sidecar is not None:
            per_paths = result.get("paths") or {}
            for ue_idx, ue_name in enumerate(ue_names):
                for cell_idx, cell_name in enumerate(cell_names):
                    trip = (per_paths.get(ue_name) or {}).get(cell_name)
                    if trip is not None:
                        sidecar.put(tick_idx, ue_idx, cell_idx, trip)

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

        # DrJit 快取歸還 —— 不做的話 RSS 只進不出,長跑必 OOM
        if (tick_idx + 1) % FLUSH_EVERY == 0:
            rss = _flush_drjit()
            print(f"[precompute] flush @ tick {tick_idx + 1}: RSS={rss}MB")

        # 斷點:存目前算到哪,被殺掉還能接
        def _save_ckpt(next_tick: int) -> None:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = ckpt_path.with_suffix(".tmp.npz")
            np.savez(str(tmp), path_gain_db=cache_3d,
                     cell_names=np.array(cell_names or []),
                     next_tick=np.int32(next_tick))
            tmp.replace(ckpt_path)      # 原子換檔,避免存到一半被殺留下壞檔
            if sidecar is not None:     # 路徑檔先落地,checkpoint 才算數
                sidecar.flush()
                sidecar.write_meta(filled_upto=int(next_tick))

        if (tick_idx + 1) % CHECKPOINT_EVERY == 0 and cache_3d is not None:
            _save_ckpt(tick_idx + 1)
            print(f"[precompute] checkpoint @ tick {tick_idx + 1}")

        # 分段收工:flush 回收不掉的殘留會愈積愈快(實測每 2000 tick 從 +74MB
        # 一路漲到 +548MB,而且還在加速),同一個行程跑不完 24 小時就會撞
        # mem_limit。做完一段就正常結束,由外層 loop 重開一個新行程接著跑 ——
        # 行程一結束記憶體全部還給 OS,等於每段都從乾淨狀態開始。
        if (segment_ticks and cache_3d is not None
                and (tick_idx + 1 - resume_from) >= segment_ticks
                and (tick_idx + 1) < total_ticks):
            _save_ckpt(tick_idx + 1)
            print(f"[precompute] segment done @ tick {tick_idx + 1} "
                  f"({(tick_idx + 1) / total_ticks * 100:.1f}%) — 交棒給下一個行程")
            return SEGMENT_EXIT_CODE

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
    # Orchestrator supplies the physical scene version at precompute launch.
    # Write after the complete NPZ; failed/partial jobs cannot certify a cache.
    if os.environ.get('CHANNEL_CACHE_FINGERPRINT'):
        manifest = out_path.with_suffix('.manifest.json')
        tmp_manifest = manifest.with_suffix('.json.tmp')
        tmp_manifest.write_text(json.dumps({'fingerprint': os.environ['CHANNEL_CACHE_FINGERPRINT'],
                                            'cache_size': size_bytes}))
        tmp_manifest.replace(manifest)
    if sidecar is not None:
        sidecar.flush()
        sidecar.write_meta(filled_upto=int(total_ticks), complete=True)

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
    ckpt_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sionna offline precompute worker")
    parser.add_argument("scenario_id", help="scenario_id from Omniverse Scenario API")
    parser.add_argument("--resume", action="store_true",
                        help="從上次的 checkpoint 接續(被 OOM/中斷後用)")
    parser.add_argument("--segment-ticks", type=int, default=0,
                        help=f"跑滿這麼多 tick 就存檔離開(exit {SEGMENT_EXIT_CODE}),"
                             "讓外層 loop 重開行程把記憶體歸零。0=不分段")
    args = parser.parse_args()
    sys.exit(run(args.scenario_id, resume=args.resume,
                 segment_ticks=args.segment_ticks))
