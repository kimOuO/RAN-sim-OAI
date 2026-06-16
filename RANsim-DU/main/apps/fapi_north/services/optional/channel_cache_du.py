"""DU-side channel cache reader(in-process Phase 1,cached mode 用)。

鏡像 RU 的 ChannelCache:讓 DU 在 cached mode **直接讀** /data/channel_cache/{scenario_id}.npz
的 path_gain,免 per-tick DU↔RU FAPI HTTP → 解放 tick 粒度(可縮 sim_dt → 修 tick-邊界 spike)。
只讀;.mode file 由 RU 寫,DU 跟著讀(cached:<scenario_id>)。純 numpy,無 RU 相依。
"""
from __future__ import annotations

import math
import os
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from main.utils.logger import get_logger

logger = get_logger(__name__)

CACHE_DIR = Path(os.environ.get("RU_CACHE_DIR", "/data/channel_cache"))
MODE_FILE = CACHE_DIR / ".mode"
# SINR 計算常數(對齊 RU dl_tti_pipeline:同 env)
_TX_POWER_DBM = float(os.environ.get("RU_TX_POWER_DBM", "23.0"))
_NOISE_FLOOR_DBM = float(os.environ.get("RU_NOISE_FLOOR_DBM", "-98.0"))
# inter-frequency 模式:不同頻 cell 互不干擾。本模型用「所有 cell 不同頻」近似
# (CCO 兩 cell 各一頻段成立)→ SINR = serving / noise(不計 cross-cell 干擾)。
# off(預設)= 原 co-channel(把所有 cell 當同頻互擾)。CCO inter-freq 換手 demo 用。
_INTER_FREQ = os.environ.get("DU_INTER_FREQ", "off").strip().lower() in ("on", "true", "1")


def set_inter_freq(enabled: bool) -> None:
    """runtime 切 inter-freq(劇本 start 時套用,免 DU 專用 env)。"""
    global _INTER_FREQ
    _INTER_FREQ = bool(enabled)


def set_tx_power_dbm(dbm: float) -> None:
    """runtime 設 TX power(劇本 start 時套用)。"""
    global _TX_POWER_DBM
    _TX_POWER_DBM = float(dbm)


def get_inter_freq() -> bool:
    """目前生效的 inter-freq 設定(供 runtime phys getter / 前端觀測)。"""
    return bool(_INTER_FREQ)


def get_tx_power_dbm() -> float:
    return float(_TX_POWER_DBM)


def get_noise_floor_dbm() -> float:
    return float(_NOISE_FLOOR_DBM)


class DuChannelCache:
    """per-scenario path_gain 查表(鏡像 RU ChannelCache.lookup)。"""

    def __init__(self, scenario_id: str):
        self.scenario_id = scenario_id
        self.path_gain_db: np.ndarray | None = None
        self.ue_names: list[str] = []
        self.cell_names: list[str] = []   # physics tx_name(如 "gnbDT#0")
        self.tick_ms: int = 500
        self.total_ticks: int = 0
        self._ue_idx: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        path = CACHE_DIR / f"{self.scenario_id}.npz"
        if not path.exists():
            raise FileNotFoundError(f"DU channel cache not found: {path}")
        d = np.load(str(path), allow_pickle=True)
        self.path_gain_db = d["path_gain_db"]
        self.ue_names = [str(x) for x in d["ue_names"].tolist()]
        self.cell_names = [str(x) for x in d["cell_names"].tolist()]
        self.tick_ms = int(d["tick_ms"])
        self.total_ticks = int(d["total_ticks"])
        self._ue_idx = {n: i for i, n in enumerate(self.ue_names)}
        logger.info(
            "DuChannelCache loaded: scenario=%s ticks=%d ues=%d cells=%d cache_tick_ms=%d",
            self.scenario_id, self.total_ticks, len(self.ue_names),
            len(self.cell_names), self.tick_ms,
        )

    def lookup(self, tick_idx: int, ue_id: str) -> tuple[dict[str, float], str | None]:
        """回傳 ({tx_name: linear_gain}, serving_tx)。ue 不在/cache 空 → ({}, None)。"""
        if self.path_gain_db is None:
            return {}, None
        ui = self._ue_idx.get(ue_id)
        if ui is None:
            return {}, None
        t = max(0, min(int(tick_idx), self.total_ticks - 1))
        row_db = self.path_gain_db[t, ui, :]
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


def read_mode() -> tuple[str, str]:
    """讀 .mode → (mode, scenario_id)。fallback env。"""
    try:
        if MODE_FILE.exists():
            txt = MODE_FILE.read_text().strip()
            if txt.startswith("cached:"):
                return "cached", txt[len("cached:"):]
            return "live", ""
    except OSError:
        pass
    return os.environ.get("RU_CHANNEL_MODE", "live").lower(), os.environ.get("RU_SCENARIO_ID", "")


def cell_id_to_tx(cell_id: str) -> str:
    """DU cell_id → physics tx_name:'gnbDT_c0' → 'gnbDT#0'。"""
    if "_c" in cell_id:
        base, n = cell_id.rsplit("_c", 1)
        return f"{base}#{n}"
    return cell_id


# tx_name → (freq_ghz, bw_mhz),從 CellState 建,2s 快取(SINR 每 tick 呼叫,免每次打 DB)。
_FREQ_MAP_CACHE: dict[str, Any] = {"ts": 0.0, "map": {}}


def _cell_freq_map() -> dict[str, tuple[float, float]]:
    now = time.time()
    if now - _FREQ_MAP_CACHE["ts"] > 2.0:
        try:
            from main.apps.mac.models.cell_state import CellState
            m: dict[str, tuple[float, float]] = {}
            for c in CellState.objects.values("cell_id", "freq_ghz", "bw_mhz"):
                m[cell_id_to_tx(c["cell_id"])] = (float(c["freq_ghz"]), float(c["bw_mhz"]))
            _FREQ_MAP_CACHE["map"] = m
            _FREQ_MAP_CACHE["ts"] = now
        except Exception:
            pass  # DB 沒 ready 等狀況:回上次快取(或空),compute_sinr_db 會 fallback co-channel
    return _FREQ_MAP_CACHE["map"]


def _freq_overlaps(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """兩 cell 頻段是否重疊(會互擾)。a/b = (freq_ghz, bw_mhz)。
    |Δf| (MHz) < (BWa + BWb)/2 → 重疊。e.g. 3.45 vs 3.65 = 200MHz > 40 → 不重疊。"""
    df_mhz = abs(a[0] - b[0]) * 1000.0
    return df_mhz < (a[1] + b[1]) / 2.0


def compute_sinr_db(path_gain_dict: dict[str, float], serving_tx: str | None) -> float:
    """對齊 RU _compute_sinr_db_with_real_interference:
    SINR = serving_rx / (Σ其他cell_rx + noise),rx_mw = TX_mW × path_gain_linear。
    假設各 cell 同 TX power(_TX_POWER_DBM,scenario 23dBm 場景成立)。"""
    if not serving_tx or serving_tx not in path_gain_dict:
        return float("-inf")
    serving_pg = path_gain_dict[serving_tx]
    if serving_pg <= 0:
        return float("-inf")
    tx_mw = 10.0 ** (_TX_POWER_DBM / 10.0)
    serving_mw = tx_mw * serving_pg
    # 干擾模型:
    #   inter_freq 旗標 True → 強制不互擾(舊劇本相容)。
    #   否則(co-channel)→ 用「頻率重疊」判斷:只有頻段和 serving 重疊的鄰 cell 才算干擾。
    #     對齊 OAI 1-gNB-2-DU 異頻(c0=3.45/c1=3.65 差 200MHz 不重疊 → 自然不互擾,免旗標);
    #     同頻劇本(全 3.5)所有 cell 都重疊 → 行為與舊版相同(零破壞)。
    if _INTER_FREQ:
        interference_mw = 0.0
    else:
        fmap = _cell_freq_map()
        sf = fmap.get(serving_tx)
        interference_mw = 0.0
        for tx, pg in path_gain_dict.items():
            if tx == serving_tx or pg <= 0:
                continue
            if sf is not None and tx in fmap and not _freq_overlaps(sf, fmap[tx]):
                continue  # 頻段不重疊 → 不互擾
            interference_mw += tx_mw * pg
    noise_mw = 10.0 ** (_NOISE_FLOOR_DBM / 10.0)
    sinr_lin = serving_mw / (interference_mw + noise_mw)
    return 10.0 * math.log10(sinr_lin) if sinr_lin > 0 else float("-inf")


def sinr_for_ue(sim_time_ms: float, ue_id: str, serving_cell_id: str | None) -> float | None:
    """in-process SINR:cached 才有。sim_time_ms → cache tick(處理 sim_dt ≠ cache_tick_ms 的映射)。"""
    c = get_du_cache()
    if c is None:
        return None
    cache_idx = int(sim_time_ms / max(c.tick_ms, 1))   # sim-time → cache tick(sim_dt 細也對得到)
    gains, best = c.lookup(cache_idx, ue_id)
    if not gains:
        return None
    serving_tx = cell_id_to_tx(serving_cell_id) if serving_cell_id else best
    if serving_tx not in gains:
        serving_tx = best   # serving cell 不在 cache → 退 argmax
    return compute_sinr_db(gains, serving_tx)


_singleton: DuChannelCache | None = None
_lock = threading.Lock()


def get_du_cache() -> DuChannelCache | None:
    """cached mode 才回 cache 物件,否則 None。"""
    mode, sid = read_mode()
    if mode != "cached" or not sid:
        return None
    global _singleton
    if _singleton is not None and _singleton.scenario_id == sid:
        return _singleton
    with _lock:
        if _singleton is not None and _singleton.scenario_id == sid:
            return _singleton
        try:
            _singleton = DuChannelCache(sid)
        except FileNotFoundError as e:
            logger.error("DU cache load failed: %s", e)
            return None
    return _singleton
