"""Phase B B.3 — Cached channel lookup for fast-replay mode.

RU_CHANNEL_MODE=cached 時,dl_tti_pipeline 不打 physics(Sionna)
改從 npz cache 撈 path_gain。下游 RSRP/SINR 計算 unchanged
(共用 rsrp_model + calibration env vars)。

Cache 檔由 Physics_sim/precompute/run_precompute.py 寫到
/data/channel_cache/{scenario_id}.npz,RU 透過 bind mount 唯讀掛載讀取。
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

import numpy as np

from main.utils.logger import get_logger


logger = get_logger(__name__)

# ray tracing 某 tick 找不到路徑 → NaN;短缺口(≤ GAP_FILL_SEC)是取樣誤差 → 線性內插;
# 長缺口視為真的沒訊號 → 低底值(仍會掉線,但不會因單一 tick 缺值就 RLF)
GAP_FILL_SEC = float(os.environ.get("CHANNEL_CACHE_GAP_FILL_SEC", "30"))
NO_PATH_FLOOR_DB = float(os.environ.get("CHANNEL_CACHE_NO_PATH_DB", "-150"))


def fill_path_gaps(g: np.ndarray, tick_ms: int) -> tuple[np.ndarray, int, int]:
    """(ticks, ues, cells) dB → 回傳 (補好的陣列, 內插點數, 補底值點數)。頭尾缺口用最近值延伸。"""
    g = np.array(g, dtype=np.float32)
    max_gap = max(1, int(GAP_FILL_SEC * 1000 / max(1, tick_ms)))
    idx = np.arange(g.shape[0])
    n_interp = n_floor = 0
    for u in range(g.shape[1]):
        for c in range(g.shape[2]):
            x = g[:, u, c]
            bad = ~np.isfinite(x)
            if not bad.any():
                continue
            if bad.all():
                x[:] = NO_PATH_FLOOR_DB
                n_floor += x.size
                continue
            d = np.diff(np.r_[0, bad.astype(np.int8), 0])
            starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
            good = ~bad
            interp = np.interp(idx, idx[good], x[good])
            for s, e in zip(starts, ends):
                if e - s <= max_gap:
                    x[s:e] = interp[s:e]
                    n_interp += e - s
                else:
                    x[s:e] = NO_PATH_FLOOR_DB
                    n_floor += e - s
    return g, n_interp, n_floor



CACHE_DIR = Path(os.environ.get("RU_CACHE_DIR", "/data/channel_cache"))
# Phase B — Gunicorn 跑 multi-worker,os.environ mutation 只改單一 worker 不對其他 worker 生效。
# 改用 disk file 當所有 worker 共用的 mode source-of-truth。
# .mode 是 RU 寫、DU 讀的 channel-mode 交接檔。channel_cache 目錄是所有 run 共用的 bind mount,
# per-run 容器(P4)必須各用各的檔,否則 A run 的 RU 一寫,B run 的 DU 就跟著切到 A 的 cache
# (2026-09-13 實測:corridor_00_08 的 DU 被切成 corridor_16_24,tick 停頓、倍速掉到 0.47×)。
# orchestrator 對同一 run 的 du/ru 都設 CHANNEL_MODE_FILE=/data/channel_cache/.mode.<rid>。
MODE_FILE = Path(os.environ.get("CHANNEL_MODE_FILE", "")) if os.environ.get("CHANNEL_MODE_FILE") else CACHE_DIR / ".mode"


class ChannelCache:
    """Per-scenario 的 path_gain 查表。Thread-safe(load 互斥;query 純讀)。"""

    def __init__(self, scenario_id: str):
        self.scenario_id = scenario_id
        self.path_gain_db: np.ndarray | None = None    # (total_ticks, n_ues, n_cells)
        self.ue_names: list[str] = []
        self.cell_names: list[str] = []                # physics tx_name(如 "gnb4#0")
        self.tick_ms: int = 500
        self.total_ticks: int = 0
        self._ue_idx: dict[str, int] = {}              # ue_name → idx
        # 階段 C:路徑參數(有 <scenario>.paths/ 才有);mmap 唯讀,多個 RU 共用 page cache
        self.paths: dict | None = None
        self._load()
        self._load_paths()

    def _load(self):
        path = CACHE_DIR / f"{self.scenario_id}.npz"
        if not path.exists():
            raise FileNotFoundError(f"Channel cache not found: {path}")
        logger.info("Loading channel cache: %s", path)
        d = np.load(str(path), allow_pickle=True)
        self.path_gain_db, n_i, n_f = fill_path_gaps(d["path_gain_db"], int(d["tick_ms"]))
        logger.info("channel cache gaps: interpolated=%d floored=%d", n_i, n_f)
        self.ue_names = [str(x) for x in d["ue_names"].tolist()]
        self.cell_names = [str(x) for x in d["cell_names"].tolist()]
        self.tick_ms = int(d["tick_ms"])
        self.total_ticks = int(d["total_ticks"])
        self._ue_idx = {n: i for i, n in enumerate(self.ue_names)}
        logger.info(
            "ChannelCache loaded: scenario=%s ticks=%d ues=%d cells=%d tick_ms=%d",
            self.scenario_id, self.total_ticks, len(self.ue_names),
            len(self.cell_names), self.tick_ms,
        )

    def _load_paths(self) -> None:
        import json
        d = CACHE_DIR / f"{self.scenario_id}.paths"
        try:
            meta = json.loads((d / "meta.json").read_text())
            if not meta.get("complete"):
                logger.warning("path sidecar %s 未完成(filled_upto=%s),cached 模式維持單天線", d, meta.get("filled_upto"))
                return
            self.paths = {
                "a": np.load(d / "a.npy", mmap_mode="r"),
                "kt": np.load(d / "kt.npy", mmap_mode="r"),
                "kr": np.load(d / "kr.npy", mmap_mode="r"),
                "ue_idx": {n: i for i, n in enumerate(meta["ue_names"])},
                "cell_idx": {n: i for i, n in enumerate(meta["cell_names"])},
                "orientation": meta.get("tx_orientation") or {},
                "ticks": int(meta["shape"][0]),
            }
            logger.info("ChannelCache paths loaded: %s K=%s ticks=%d", d, meta.get("top_k"), self.paths["ticks"])
        except FileNotFoundError:
            self.paths = None
        except Exception as exc:  # noqa: BLE001 — 路徑檔壞了就退回舊行為,不影響 path gain
            logger.warning("path sidecar %s 讀取失敗:%s", d, exc)
            self.paths = None

    def lookup_paths(self, tick_idx: int, ue_id: str, tx_name: str):
        """回傳 (A (K,2,2), k_t (K,3), k_r (K,3), tx_orientation) 或 None。"""
        p = self.paths
        if p is None:
            return None
        ui, ci = p["ue_idx"].get(ue_id), p["cell_idx"].get(tx_name)
        if ui is None or ci is None:
            return None
        t = max(0, min(int(tick_idx), p["ticks"] - 1))
        a = np.asarray(p["a"][t, ui, ci])
        if not np.any(a):
            return None   # 這個 tick 沒追到路徑
        return (a, np.asarray(p["kt"][t, ui, ci], dtype=np.float64),
                np.asarray(p["kr"][t, ui, ci], dtype=np.float64), tuple(p["orientation"].get(tx_name, (0.0, 0.0, 0.0))))

    def lookup(
        self, tick_idx: int, ue_id: str,
    ) -> tuple[dict[str, float], str | None]:
        """回傳 (path_gain_linear_dict, serving_tx_name).

        path_gain_linear_dict: {tx_name: linear_gain},NaN entries 過濾掉。
        serving_tx_name: 該 UE 對應到 max linear gain 的 tx_name。

        若 ue_id 不在 cache (e.g. 跑了沒 precompute 的 UE),回 ({}, None)。
        tick_idx 超出範圍 → clamp 到最後一個 tick。
        """
        if self.path_gain_db is None:
            return {}, None
        ue_idx = self._ue_idx.get(ue_id)
        if ue_idx is None:
            return {}, None
        # clamp tick_idx
        t = max(0, min(int(tick_idx), self.total_ticks - 1))
        row_db = self.path_gain_db[t, ue_idx, :]   # (n_cells,)

        gains: dict[str, float] = {}
        best_tx: str | None = None
        best_lin = 0.0
        for ci, tx_name in enumerate(self.cell_names):
            db = float(row_db[ci])
            if not np.isfinite(db):
                continue
            lin = 10.0 ** (db / 10.0)
            gains[tx_name] = lin
            if lin > best_lin:
                best_lin = lin
                best_tx = tx_name
        return gains, best_tx


_singleton: ChannelCache | None = None
_lock = threading.Lock()


def get_channel_cache() -> ChannelCache | None:
    """Lazy load cache by RU_SCENARIO_ID env. Returns None if mode != cached.

    呼叫前先 check `is_cached_mode()`;若 mode=live 不應該叫這個。
    """
    global _singleton
    if not is_cached_mode():
        return None
    if _singleton is not None and _singleton.scenario_id == _current_scenario_id():
        return _singleton
    with _lock:
        # double-check
        if _singleton is not None and _singleton.scenario_id == _current_scenario_id():
            return _singleton
        scenario_id = _current_scenario_id()
        if not scenario_id:
            logger.warning("RU_CHANNEL_MODE=cached but RU_SCENARIO_ID not set")
            return None
        try:
            _singleton = ChannelCache(scenario_id)
        except FileNotFoundError as e:
            logger.error("Channel cache load failed: %s", e)
            return None
    return _singleton


def _read_mode_file() -> tuple[str, str]:
    """讀 .mode file 回 (mode, scenario_id). File 不存在/壞掉就 fallback env。"""
    try:
        if MODE_FILE.exists():
            txt = MODE_FILE.read_text().strip()
            if txt == "live" or not txt:
                return "live", ""
            if txt.startswith("cached:"):
                return "cached", txt[len("cached:"):]
    except OSError:
        pass
    return (
        os.environ.get("RU_CHANNEL_MODE", "live").lower(),
        os.environ.get("RU_SCENARIO_ID", ""),
    )


def write_mode_file(mode: str, scenario_id: str = "") -> None:
    """RuController.set_channel_mode 呼叫,把 mode 寫到 disk 給所有 worker 看到。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if mode == "cached" and scenario_id:
        MODE_FILE.write_text(f"cached:{scenario_id}")
    else:
        MODE_FILE.write_text("live")


def is_cached_mode() -> bool:
    mode, _ = _read_mode_file()
    return mode == "cached"


def _current_scenario_id() -> str:
    _, sid = _read_mode_file()
    return sid


def reload_cache() -> ChannelCache | None:
    """強制重新載入 (e.g. scenario 換了)。"""
    global _singleton
    with _lock:
        _singleton = None
    return get_channel_cache()
