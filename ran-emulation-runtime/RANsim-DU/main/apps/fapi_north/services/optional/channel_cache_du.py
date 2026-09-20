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


# 每個 tick 各自 ray tracing,相鄰 0.5 s 的 path gain 平均跳 ~14 dB(射線取樣雜訊),
# 真實大尺度衰落不會變這麼快 → 以置中移動平均(dB)平滑;0 = 不平滑
SMOOTH_SEC = float(os.environ.get("CHANNEL_CACHE_SMOOTH_SEC", "10"))


def smooth_path_gain(g: np.ndarray, tick_ms: int) -> np.ndarray:
    w = int(round(SMOOTH_SEC * 1000 / max(1, tick_ms)))
    if w < 2 or g.shape[0] < w:
        return g
    c = np.cumsum(np.concatenate([np.zeros((1,) + g.shape[1:], np.float64), g.astype(np.float64)]), axis=0)
    out = g.copy()
    h = w // 2
    avg = (c[w:] - c[:-w]) / w                     # avg[i] = mean(g[i:i+w])
    out[h:h + avg.shape[0]] = avg.astype(np.float32)
    return out


CACHE_DIR = Path(os.environ.get("RU_CACHE_DIR", "/data/channel_cache"))
# .mode 是 RU 寫、DU 讀的 channel-mode 交接檔。channel_cache 目錄是所有 run 共用的 bind mount,
# per-run 容器(P4)必須各用各的檔,否則 A run 的 RU 一寫,B run 的 DU 就跟著切到 A 的 cache
# (2026-09-13 實測:corridor_00_08 的 DU 被切成 corridor_16_24,tick 停頓、倍速掉到 0.47×)。
# orchestrator 對同一 run 的 du/ru 都設 CHANNEL_MODE_FILE=/data/channel_cache/.mode.<rid>。
MODE_FILE = Path(os.environ.get("CHANNEL_MODE_FILE", "")) if os.environ.get("CHANNEL_MODE_FILE") else CACHE_DIR / ".mode"
# SINR 計算常數(對齊 RU dl_tti_pipeline:同 env)
_TX_POWER_DBM = float(os.environ.get("RU_TX_POWER_DBM", "23.0"))
# 2026-09-21:舊值 -98.0 是 40 MHz 的熱雜訊但 NF=0 dB(真實 UE 7~9 dB),而且不隨
# cell 頻寬變。改成由 PRB 數 × SCS 推導 + UE 雜訊指數;RU_NOISE_FLOOR_DBM 設了就沿用
# 該值(回退用)。上行與 physics coverage 本來就有推導,只有下行漏掉。
def _derive_noise_floor() -> float:
    override = os.environ.get("RU_NOISE_FLOOR_DBM", "").strip()
    if override:
        return float(override)
    from ran_sim_protocol.rsrp_model import downlink_noise_floor_dbm, scs_hz_from_numerology
    n_prb = int(os.environ.get("SIM_DEFAULT_PRB_PER_CELL", "106"))
    slots = int(os.environ.get("SIM_SLOTS_PER_FRAME", "20"))      # 10 × 2^μ
    mu = max(0, (slots // 10).bit_length() - 1)
    nf = float(os.environ.get("UE_NOISE_FIGURE_DB", "7.0"))
    return downlink_noise_floor_dbm(n_prb, scs_hz_from_numerology(mu), nf)


_NOISE_FLOOR_DBM = _derive_noise_floor()
# 收發機失真上限(對齊 RU dl_tti_pipeline._apply_evm_lin,同 env):TS 38.104 §6.5.2 256QAM EVM ≤ 3.5%
# → SNR 上限 ≈ 29 dB。1/SINR_eff = 1/SINR + 1/SNR_evm。設 0 關掉。
_EVM_SNR_DB = float(os.environ.get("RU_EVM_SNR_DB", "29.1"))
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
        self.path_gain_db, n_i, n_f = fill_path_gaps(d["path_gain_db"], int(d["tick_ms"]))
        self.path_gain_db = smooth_path_gain(self.path_gain_db, int(d["tick_ms"]))
        logger.info("channel cache gaps: interpolated=%d floored=%d", n_i, n_f)
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
    """DU cell_id → physics tx_name。run 標籤('e01:gnbDT_c0')先剝掉,npz 的 tx 名沒有它。

    對應規則(2026-09-19 修):以**載入的 cache 實際有的 tx 名**為準,再退回命名規則。
    以前只處理 'gnbDT_c0' → 'gnbDT#0';走廊那種 cell 名是 'src' / 'nbr'(沒有 _c)時
    會回 'src',但 cache 的鍵是 'src#0' → 永遠對不上 → sinr_for_ue 一路退回 argmax,
    UE 掛在沒訊號的 cell 上卻回報最強 cell 的 SINR(實測 RSRP −140 / SINR 29 dB)。
    """
    from ran_sim_protocol.cell_tag import strip_tag
    cell_id = strip_tag(cell_id)
    c = get_du_cache()
    names = list(getattr(c, "cell_names", []) or []) if c is not None else []
    if cell_id in names:
        return cell_id
    for n in names:                      # 'src' → 'src#0'(tx 名是 <cell>#<pci>)
        if n.split("#", 1)[0] == cell_id:
            return n
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


# 下行干擾的鄰 cell 負載:沒給(舊呼叫端)= 滿載;有給但缺某 cell = 只剩參考訊號 / 控制通道的下限
DL_MIN_LOAD = float(os.environ.get("DL_MIN_NEIGHBOR_LOAD", "0.1"))
# 服務 cell 在這個 tick 完全沒有路徑時回報的 SINR(低於 RLF 門檻 → 正常觸發斷線流程)
_NO_SERVING_SINR_DB = float(os.environ.get("DU_NO_SERVING_SINR_DB", "-30"))


def compute_sinr_db(path_gain_dict: dict[str, float], serving_tx: str | None, extra_gain_db: float = 0.0,
                    load_by_tx: dict[str, float] | None = None) -> float:
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
            rho = 1.0 if load_by_tx is None else max(DL_MIN_LOAD, min(1.0, load_by_tx.get(tx, 0.0)))
            interference_mw += tx_mw * pg * rho
    noise_mw = 10.0 ** (_NOISE_FLOOR_DBM / 10.0)
    sinr_lin = serving_mw / (interference_mw + noise_mw) * 10.0 ** (float(extra_gain_db or 0.0) / 10.0)   # 陣列增益在失真上限之前
    if _EVM_SNR_DB > 0 and sinr_lin > 0:
        sinr_lin = 1.0 / (1.0 / sinr_lin + 10.0 ** (-_EVM_SNR_DB / 10.0))
    return 10.0 * math.log10(sinr_lin) if sinr_lin > 0 else float("-inf")


def sinr_for_ue(sim_time_ms: float, ue_id: str, serving_cell_id: str | None, extra_gain_db: float = 0.0,
                cell_load: dict[str, float] | None = None) -> float | None:
    """in-process SINR:cached 才有。sim_time_ms → cache tick(處理 sim_dt ≠ cache_tick_ms 的映射)。"""
    c = get_du_cache()
    if c is None:
        return None
    cache_idx = int(sim_time_ms / max(c.tick_ms, 1))   # sim-time → cache tick(sim_dt 細也對得到)
    gains, best = c.lookup(cache_idx, ue_id)
    if not gains:
        return None
    if not serving_cell_id:
        serving_tx = best            # 還沒附著:用最強的當觀測值
    else:
        serving_tx = cell_id_to_tx(serving_cell_id)
        if serving_tx not in gains:
            # 服務 cell 這個 tick 沒有路徑 = 真的收不到。以前偷換成最強 cell,
            # 結果 UE 掛在死掉的 cell 上卻回報別人的 SINR,RLF 永遠不觸發(2026-09-19)。
            return float(_NO_SERVING_SINR_DB)
    load_by_tx = None if cell_load is None else {cell_id_to_tx(c): v for c, v in cell_load.items()}
    return compute_sinr_db(gains, serving_tx, extra_gain_db, load_by_tx)


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
