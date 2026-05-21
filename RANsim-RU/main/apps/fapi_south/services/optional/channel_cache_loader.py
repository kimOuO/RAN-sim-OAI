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


CACHE_DIR = Path(os.environ.get("RU_CACHE_DIR", "/data/channel_cache"))
# Phase B — Gunicorn 跑 multi-worker,os.environ mutation 只改單一 worker 不對其他 worker 生效。
# 改用 disk file 當所有 worker 共用的 mode source-of-truth。
MODE_FILE = CACHE_DIR / ".mode"   # 內容:"live" 或 "cached:<scenario_id>"


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
        self._load()

    def _load(self):
        path = CACHE_DIR / f"{self.scenario_id}.npz"
        if not path.exists():
            raise FileNotFoundError(f"Channel cache not found: {path}")
        logger.info("Loading channel cache: %s", path)
        d = np.load(str(path), allow_pickle=True)
        self.path_gain_db = d["path_gain_db"]
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
