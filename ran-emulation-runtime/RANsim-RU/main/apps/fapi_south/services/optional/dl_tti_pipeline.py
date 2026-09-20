"""DL TTI pipeline — Physics → Beamforming → SINR/CQI → DU callback。

對應 OAI: nr-ru.c::ru_thread() 收到 nFAPI DL request 後的處理鏈，
但這裡不真做 IFFT/RF；只算 UE-side SINR 量測。
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from django.conf import settings
from ran_sim_protocol.fapi import CqiIndication, DlTtiRequest
from ran_sim_protocol.physics import PathSolverResponse

from main.apps.beamforming.services.optional import array_chain, codebook, codebook_type1, csi_selection, gob, precoder, sinr_estimator, virtualization
from main.apps.fapi_south.services.optional import live_smoothing
from main.apps.fapi_south.services.optional.channel_cache_loader import (
    get_channel_cache, is_cached_mode,
)
from main.apps.physics_client.services.optional import physics_http
from main.apps.physics_client.services.optional.channel_cache import default_cache, quantize_position
from main.apps.physics_client.services.optional.payload_builder import build_path_solver_request
from main.utils.env_loader import get_bool, get_float, get_int
from main.utils.logger import get_logger


logger = get_logger(__name__)


# 2026-09-21:見 DU channel_cache_du._derive_noise_floor 的說明 —— 舊值 -98.0 的 NF 是 0 dB。
def _derive_noise_floor() -> float:
    import os

    from ran_sim_protocol.rsrp_model import downlink_noise_floor_dbm, scs_hz_from_numerology
    override = os.environ.get("RU_NOISE_FLOOR_DBM", "").strip()
    if override:
        return float(override)
    n_prb = int(os.environ.get("SIM_DEFAULT_PRB_PER_CELL", "106"))
    slots = int(os.environ.get("SIM_SLOTS_PER_FRAME", "20"))
    mu = max(0, (slots // 10).bit_length() - 1)
    return downlink_noise_floor_dbm(n_prb, scs_hz_from_numerology(mu),
                                    get_float("UE_NOISE_FIGURE_DB", default=7.0))


_NOISE_FLOOR_DBM = _derive_noise_floor()
# Fallback TX power 給沒 Cell DB record 的極早期啟動階段；正常運行讀 Cell.power_dbm。
_TX_POWER_DBM_FALLBACK = get_float("RU_TX_POWER_DBM", default=23.0)
_NEIGHBOR_RSRP_FLOOR_DBM = get_float("RU_NEIGHBOR_RSRP_FLOOR_DBM", default=-120.0)
"""比 -120 dBm 弱的 neighbor 不報，避免 A3 evaluator 看一堆 noise。"""

# scene calibration loss — sim Brownstone 場景比真實 urban 環境少模擬以下損耗:
#   • building penetration (UE 在室內, 18-25 dB)
#   • body loss / clutter (UE 拿手裡或包裡, 5-10 dB)
#   • shadowing fade (lognormal, ~8 dB σ)
# 加總約 36 dB。對映 3GPP TR 38.901 §7.4.3.1 O2I loss + shadowing。
#
# 歷史值是 50 dB，因為當時又 +14 dBi antenna_gain（與 Sionna PlanarArray 內建增益
# 重複計算），實際淨損耗是 36 dB。AK8 改成 per-cell power 後拔掉雙重 gain，
# 此值直接命名為「真實場景損耗」，與 ran_sim_protocol.rsrp_model 共用。
_SCENE_CALIBRATION_LOSS_DB = get_float("RU_SCENE_CALIBRATION_LOSS_DB", default=0.0)
"""真實場景額外損耗 (Brownstone 場景沒模擬到的 O2I + body + shadowing)."""

# SINR 校正:過去用固定 20 dB hack 補「sim 沒算 inter-cell interference」。改用真實
# 從 path_gain_dict 算多 cell 干擾(task #91)後 penalty 預設 0,只保留 env 給特殊
# 需求(例如想額外模擬 multipath fading)拉一點點。
_SINR_INTERFERENCE_PENALTY_DB = get_float("RU_SINR_INTERFERENCE_PENALTY_DB", default=0.0)
"""額外 SINR fade margin。預設 0(真實 interference 已從多 cell path_gain 算)."""

# 收發機失真上限(2026-09-16):純物理 SNR 在近距離 LOS 會到 60–79 dB,真實系統做不到。
# TS 38.104 §6.5.2(BS)與 TS 38.101-1 §6.4.2.1(UE)規定 256QAM 的 EVM ≤ 3.5%,
# 等於發射端自帶一個 SNR 上限 −20·log10(0.035) ≈ 29 dB。失真跟雜訊一樣當成獨立加性:
#     1/SINR_eff = 1/SINR + 1/SNR_evm
# 所以 SINR 高時被壓向 29 dB,低時幾乎不變。設 0 可關掉(回到舊行為)。
_EVM_SNR_DB = get_float("RU_EVM_SNR_DB", default=29.1)


def _apply_evm_lin(sinr_lin: float) -> float:
    """線性 SINR → 含失真上限的線性 SINR(+inf 也會被壓到上限)。"""
    if _EVM_SNR_DB <= 0 or not sinr_lin > 0:
        return sinr_lin
    return 1.0 / (1.0 / sinr_lin + 10.0 ** (-_EVM_SNR_DB / 10.0))


def _apply_evm_db(sinr_db: float) -> float:
    if _EVM_SNR_DB <= 0 or sinr_db == -float("inf"):
        return sinr_db
    lin = float("inf") if sinr_db == float("inf") else 10.0 ** (sinr_db / 10.0)
    return 10.0 * math.log10(max(_apply_evm_lin(lin), 1e-30))


# ── 上行(P6,計畫 §13)──────────────────────────────────────────────
# UE 開迴路功控(TS 38.213 §7.1.1):P_perPRB = min(P_CMAX − 10log10 M_ref, P0 + α·PL)。
_UL_P0_DBM = get_float("RU_UL_P0_DBM", default=-90.0)          # 每 PRB 目標接收功率(常見 −90…−100)
_UL_ALPHA = get_float("RU_UL_ALPHA", default=0.8)               # 部分路損補償係數
_UL_PCMAX_DBM = get_float("RU_UL_PCMAX_DBM", default=23.0)      # UE power class 3
_UL_M_REF_PRB = get_float("RU_UL_M_REF_PRB", default=10.0)      # 分攤 P_CMAX 的參考 PRB 數(RU 不知道 DU 排幾個)
# gNB 端每 PRB 雜訊:−174 dBm/Hz + 10log10(12×30 kHz) + NF 5 dB ≈ −113.4 dBm
_UL_NOISE_PER_PRB_DBM = get_float("RU_UL_NOISE_PER_PRB_DBM", default=-113.4)
# 鄰 cell UE 在同 PRB 上發射的機率(= 該 cell UL PRB 負載);RU 不知道各 DU 的 UL 排程,先用常數,之後可由 DU 推
_UL_NEIGHBOR_LOAD = get_float("RU_UL_NEIGHBOR_LOAD", default=0.5)


def _ul_tx_power_per_prb_dbm(pg_serv_linear: float) -> float:
    pl_db = -10.0 * math.log10(max(pg_serv_linear, 1e-30))
    return min(_UL_PCMAX_DBM - 10.0 * math.log10(max(_UL_M_REF_PRB, 1.0)), _UL_P0_DBM + _UL_ALPHA * pl_db)


def _build_cell_to_ul_load_map(req_map: dict | None = None) -> dict[str, float]:
    if req_map:   # DU 每 tick 帶的 cell_ul_load(2026-09-16:不再經 DB)
        return {str(k): float(v) for k, v in req_map.items()}
    try:
        from main.apps.antenna.models.cell import Cell
        return {c.name: float(c.ul_load) for c in Cell.objects.all()}
    except Exception:  # noqa: BLE001
        return {}


def _compute_ul_sinr_db(ul_ctx: dict, cell_to_freq: dict, inter_freq: bool, cell_ul_load: dict | None = None) -> dict[str, float]:
    """每個 UE 的上行 SINR@其 serving gNB。
    ul_ctx[ue] = {serving: cell_id, serving_tx: tx_name, pg_serv: linear, pg: {tx_name: linear}}
    干擾 = Σ 其他 cell 的 UE_v:P_v × pg(v → 我的 serving tx) × ρ;inter_freq 時只算同頻 cell。"""
    out: dict[str, float] = {}
    noise_mw = 10.0 ** (_UL_NOISE_PER_PRB_DBM / 10.0)
    ptx = {u: _ul_tx_power_per_prb_dbm(c["pg_serv"]) for u, c in ul_ctx.items() if c.get("pg_serv")}
    for u, c in ul_ctx.items():
        if not c.get("pg_serv") or not c.get("serving_tx"):
            continue
        sig_mw = 10.0 ** ((ptx[u] + 10.0 * math.log10(c["pg_serv"])) / 10.0)
        f_u = (cell_to_freq or {}).get(c["serving"])
        interf_mw = 0.0
        for v, cv in ul_ctx.items():
            if v == u or cv.get("serving") == c["serving"] or v not in ptx:
                continue
            if inter_freq:
                f_v = (cell_to_freq or {}).get(cv["serving"])
                if f_u and f_v and abs(float(f_u[0]) - float(f_v[0])) > 1e-6:
                    continue
            pg_v_to_me = cv["pg"].get(c["serving_tx"])
            if not isinstance(pg_v_to_me, (int, float)) or pg_v_to_me <= 0:
                continue
            rho = (cell_ul_load or {}).get(cv["serving"])
            rho = float(rho) if rho is not None else _UL_NEIGHBOR_LOAD   # DU 有推負載就用真的,否則 env 常數
            interf_mw += 10.0 ** ((ptx[v] + 10.0 * math.log10(pg_v_to_me)) / 10.0) * rho
        out[u] = _apply_evm_db(10.0 * math.log10(sig_mw / (noise_mw + interf_mw)))
    return out

# inter-frequency:True = 各 cell 不同頻不互擾 → SINR 只算訊號/噪聲(不累加他 cell 干擾)。
# 對齊 DU channel_cache_du 的 _INTER_FREQ;live mode 也要吃劇本 inter_freq(否則 cell 邊界
# co-channel 把 SINR 算崩,跟 cached 差 ~20dB)。
#
# ★ 用「共享檔」不用 process 全域變數:RU 跑 gunicorn --workers 2,Python 全域變數每個
#   worker 各一份。set_inter_freq 的 HTTP POST 只命中 1 個 worker,但算 SINR 的請求可能落到
#   另一個 worker → flag 沒生效(這是 live inter_freq 失效、跟 cached 差 16dB 的 root cause)。
#   仿 channel_cache_loader 的 .mode 檔:寫檔讓所有 worker 共讀。
import os as _os
from pathlib import Path as _Path
_INTER_FREQ_FILE = _Path(_os.environ.get("RU_CACHE_DIR", "/data/channel_cache")) / ".inter_freq"
_inter_freq_cache: dict = {"mtime": None, "val": get_bool("RU_INTER_FREQ", default=False)}


def _read_inter_freq() -> bool:
    """讀共享檔(mtime 快取,免每次 disk read)。檔不存在 → env 預設。所有 worker 共讀同一份。"""
    try:
        mt = _INTER_FREQ_FILE.stat().st_mtime
        if _inter_freq_cache["mtime"] != mt:
            _inter_freq_cache["val"] = _INTER_FREQ_FILE.read_text().strip().lower() in ("on", "true", "1")
            _inter_freq_cache["mtime"] = mt
        return _inter_freq_cache["val"]
    except FileNotFoundError:
        return get_bool("RU_INTER_FREQ", default=False)
    except Exception:
        return _inter_freq_cache["val"]


def set_inter_freq(enabled: bool) -> None:
    """runtime 設 inter_freq → 寫共享檔(所有 worker 共讀,解 multi-worker 隔離)。"""
    try:
        _INTER_FREQ_FILE.parent.mkdir(parents=True, exist_ok=True)
        _INTER_FREQ_FILE.write_text("on" if enabled else "off")
    except Exception as _e:  # noqa: BLE001
        logger.warning("set_inter_freq write file failed: %s", _e)


# 下行干擾加權(2026-09-19):以前鄰 cell 一律當滿載發射,同頻密集場景(OSM 6 cell / 260 m)輕載也 SINR < −6 dB 一直 RLF。
_DL_NEIGHBOR_LOAD_FALLBACK = float(_os.environ.get("RU_DL_NEIGHBOR_LOAD", "1.0"))   # DU 沒送負載時
_DL_MIN_NEIGHBOR_LOAD = float(_os.environ.get("DL_MIN_NEIGHBOR_LOAD", "0.1"))        # SSB / CSI-RS / PDCCH 一直在發


def _compute_sinr_db_with_real_interference(
    *,
    path_gain_dict: dict[str, float],
    serving_tx: str | None,
    serving_gnb: str | None,
    tx_to_cell: dict[str, str],
    gnb_to_cell: dict[str, str],
    cell_to_power: dict[str, float],
    cell_to_freq: dict | None = None,
    cell_dl_load: dict[str, float] | None = None,
) -> float:
    """從 path_gain_dict 算真實 SINR(含真正 inter-cell interference)。

    formula: SINR = serving_rx / (sum_other_cells_rx + noise),全部 linear mW。

    Sionna PathSolver 對每個 (TX, RX) pair 算出 path_gain(含 antenna pattern,
    不含 TX power)。組成 SINR 是我們 RU 的工作。以前用固定 -20 dB 一刀切補,
    現在這個 helper 把 path_gain_dict 內**所有**非 serving cell 的訊號加總當干擾,
    更貼近真實 RAN(UE 在 cell center → 干擾自然低、SINR 高;在 cell edge 反之)。

    各 cell 的 received signal_mW = TX_power_mW × path_gain_linear。

    注意:這裡 **不套 scene_loss**,跟 live mode `sinr_estimator.estimate_sinr` 一致
    (那邊 H matrix 也沒 scene_loss)。scene_loss 是 RSRP 顯示用的真實環境校正
    (body / O2I / shadowing),只在 _path_gain_to_rsrp_dbm 套一次。SINR 純 sim
    內部 ratio,套了反而會跟 live 不一致(差 ~36 dB)。
    """
    if not serving_tx and not serving_gnb:
        return -float("inf")
    # 抓 serving cell 的 path_gain(優先 tx_name,沒 hit 退 gnb_name)
    serving_key = serving_tx if serving_tx in path_gain_dict else serving_gnb
    serving_pg = path_gain_dict.get(serving_key)
    if not isinstance(serving_pg, (int, float)) or serving_pg <= 0:
        return -float("inf")

    def _power_for_tx(tx_name: str) -> float:
        cell_id = tx_to_cell.get(tx_name) or gnb_to_cell.get(tx_name)
        if cell_id and cell_id in cell_to_power:
            return cell_to_power[cell_id]
        return _TX_POWER_DBM_FALLBACK

    def _rx_mw(pg: float, tx_power_dbm: float) -> float:
        tx_mw = 10.0 ** (tx_power_dbm / 10.0)
        return tx_mw * pg

    serving_mw = _rx_mw(serving_pg, _power_for_tx(serving_key))

    # serving cell 的頻段(用於 co-channel 頻率重疊判斷)
    _fmap = cell_to_freq or {}
    _serv_cell = tx_to_cell.get(serving_key) or gnb_to_cell.get(serving_key)
    _serv_freq = _fmap.get(_serv_cell) if _serv_cell else None

    def _overlaps(tx_name: str) -> bool:
        """鄰 cell 頻段是否和 serving 重疊(重疊才互擾)。未知頻率 → 保守當重疊。"""
        if _serv_freq is None:
            return True
        cid = tx_to_cell.get(tx_name) or gnb_to_cell.get(tx_name)
        fo = _fmap.get(cid) if cid else None
        if fo is None:
            return True
        return abs(_serv_freq[0] - fo[0]) * 1000.0 < (_serv_freq[1] + fo[1]) / 2.0

    def _neighbor_load(tx_name: str) -> float:
        """鄰 cell 下行負載(PRB 佔用率):舊 DU 沒送 → 滿載假設;有送但缺這個 cell → 只剩參考訊號的下限。"""
        if not cell_dl_load:
            return _DL_NEIGHBOR_LOAD_FALLBACK
        cid = tx_to_cell.get(tx_name) or gnb_to_cell.get(tx_name)
        return max(_DL_MIN_NEIGHBOR_LOAD, min(1.0, cell_dl_load.get(cid, 0.0)))

    interference_mw = 0.0
    if not _read_inter_freq():  # inter_freq=True(共享檔)→ 強制不互擾(舊劇本相容)
        for tx_name, pg in path_gain_dict.items():
            if tx_name == serving_key:
                continue
            if not isinstance(pg, (int, float)) or pg <= 0:
                continue
            if not _overlaps(tx_name):   # co-channel 但頻段不重疊(異頻)→ 不互擾
                continue
            interference_mw += _rx_mw(pg, _power_for_tx(tx_name)) * _neighbor_load(tx_name)

    noise_mw = 10.0 ** (_NOISE_FLOOR_DBM / 10.0)
    denom = interference_mw + noise_mw
    if denom <= 0:
        return float("inf")
    sinr_linear = serving_mw / denom
    if sinr_linear <= 0:
        return -float("inf")
    return 10.0 * math.log10(sinr_linear)


def _build_gnb_to_cell_map() -> dict[str, str]:
    """Sionna response 的 path_gain key 是 gnb_name（聚合同 gNB 的 cells），
    但 CU/DU 的 cell_id 是「cell-level」名字（如 gnb_A_c0）。
    A3 evaluator 跟 HandoverEvent 都要 cell_id 不要 gnb_name。
    這裡查 Cell DB 把 gnb_id → 第一個對應的 cell.name 對應好。
    """
    try:
        from main.apps.antenna.models.cell import Cell
        mapping: dict[str, str] = {}
        for cell in Cell.objects.all():
            if cell.gnb_id and cell.gnb_id not in mapping:
                mapping[cell.gnb_id] = cell.name
        return mapping
    except Exception:
        return {}


def _build_cell_to_gnb_map() -> dict[str, str]:
    """cell_name → gnb_name (sim 用內部 gnb_id, 通常等於 Sionna gnb name 因 AK6 動態 chain).

    保留供 backward-compat / debug (AI3 fallback 還會走 gnb-level)。
    """
    try:
        from main.apps.antenna.models.cell import Cell
        return {c.name: c.gnb_id for c in Cell.objects.all() if c.gnb_id}
    except Exception:
        return {}


def _build_cell_to_tx_map() -> dict[str, str]:
    """sim cell_name (gnb4_c0) → Sionna tx_name (gnb4#PCI).

    AK7: Sionna engine 改成 per-tx 不聚合後, path_gain dict key 是 tx_name
    (= '${gnb_name}#${pci}'), 不再是 gnb_name. RU 端用 sim cell 的 pci field
    構造對應 tx_name 來 lookup, 拿到 cell-level path_gain (不被 max 聚合).
    """
    try:
        from main.apps.antenna.models.cell import Cell
        out: dict[str, str] = {}
        for c in Cell.objects.all():
            if c.gnb_id is None or c.pci is None:
                continue
            out[c.name] = f"{c.gnb_id}#{int(c.pci)}"
        return out
    except Exception:
        return {}


def _build_cell_to_power_map() -> dict[str, float]:
    """sim cell_name → TX power (dBm)，從 Cell DB 撈，Dashboard 透過 update_cells 推進來。

    AK8: 解決 power_dbm 從 Dashboard 改了 RU 卻沒反映的問題 — 過去 RU 永遠用
    env _TX_POWER_DBM=43，per-gNB power 只在 Coverage Solver 端有效，兩條
    pipeline 結果背離。現在 RU 也讀 Cell.power_dbm，跟 Coverage 同源。
    """
    try:
        from main.apps.antenna.models.cell import Cell
        return {c.name: float(c.power_dbm) for c in Cell.objects.all()}
    except Exception:
        return {}


def _build_cell_to_freq_map() -> dict:
    """cell.name → (frequency_ghz, bandwidth_mhz)。用於 co-channel 的頻率重疊干擾判斷
    (對齊 OAI 1-gNB-2-DU 異頻:頻段不重疊的鄰 cell 不互擾,免 inter_freq 旗標)。"""
    try:
        from main.apps.antenna.models.cell import Cell
        return {c.name: (float(c.frequency_ghz), float(c.bandwidth_mhz)) for c in Cell.objects.all()}
    except Exception:
        return {}


def _path_gain_to_rsrp_dbm(
    path_gain_linear: float,
    *,
    cell_power_dbm: float | None = None,
) -> float:
    """從 Sionna path_gain 算 RSRP (dBm)，走平台共用 rsrp_model（單一事實源）。

    AK8: 改成呼叫 ran_sim_protocol.rsrp_model.compute_rsrp_dbm，跟 Coverage
    Solver 用同一個公式，避免兩條 pipeline 計算規則分歧。同時把過去 +14 dBi
    antenna gain 雙重計算的問題拔掉（Sionna PlanarArray 已內建天線 pattern）。

    Args:
        path_gain_linear: Sionna 線性 path gain（含天線 pattern，不含 TX 功率）。
        cell_power_dbm: 該 cell 的 TX 功率（從 Cell.power_dbm DB 讀）。
            None 時退到 env fallback，保留早期啟動 / 測試環境的相容。
    """
    from ran_sim_protocol.rsrp_model import compute_rsrp_dbm

    tx_power = cell_power_dbm if cell_power_dbm is not None else _TX_POWER_DBM_FALLBACK
    return compute_rsrp_dbm(
        path_gain_linear,
        tx_power_dbm=tx_power,
        scene_loss_db=_SCENE_CALIBRATION_LOSS_DB,
    )


_MAX_RANK = get_int("RU_MAX_RANK", 4)   # cell 預設最大層數;per-cell 可由 E2 控制覆寫
_BEAM_CTRL_CACHE: dict[str, object] = {"at": 0.0, "map": {}}


def _beam_ctrl(cell_name: str) -> dict:
    """B2:某個 cell 目前的波束控制狀態(RIC 可改;2 秒快取)。"""
    import time as _t
    now = _t.time()
    if now - float(_BEAM_CTRL_CACHE["at"] or 0) > 2.0:
        try:
            from main.apps.antenna.models.cell import Cell
            _BEAM_CTRL_CACHE["map"] = {
                c.name: {"etilt": float(c.electrical_tilt_deg or 0.0),
                         "beams": list(c.active_beam_ids or []),
                         "max_layers": int(c.max_layers or 0),
                         "trx_ratio": float(getattr(c, "trx_active_ratio", 1.0) or 1.0),
                         "taper": str(getattr(c, "beam_taper", "") or ""),
                         "beam_pwr": dict(getattr(c, "beam_power_offsets_db", None) or {})}
                for c in Cell.objects.all()
            }
        except Exception:  # noqa: BLE001
            _BEAM_CTRL_CACHE["map"] = {}
        _BEAM_CTRL_CACHE["at"] = now
    return (_BEAM_CTRL_CACHE["map"] or {}).get(cell_name) or {"etilt": 0.0, "beams": [], "max_layers": 0,
                                                              "trx_ratio": 1.0, "taper": "", "beam_pwr": {}}
_CSI_CACHE: dict[tuple, dict] = {}
_CSI_CACHE_MAX = 512


def _cat_b_select(H: np.ndarray, beam, gamma_ref_lin: float, layout, max_rank: int = 4) -> dict:
    """O-RAN Cat B predefined-beam:波束由 O-RU 的 GoB 決定,只在該波束上挑層數。

    rank 1 = 兩個極化同相送一道波束;rank 2 = 同一道波束用雙極化送兩層
    (mMIMO 做 SU-MIMO 的標準作法)。`pmi` 回報 beam_id —— Cat B 不走 UE 的 PMI 回報。
    """
    n1, n2 = layout
    o1, o2 = codebook_type1.oversampling(n1, n2)
    Hn = csi_selection.normalize(H)
    He1 = Hn @ beam.weights
    g1 = csi_selection.layer_sinr(He1, gamma_ref_lin)
    rank1_gain = float(np.sum(np.abs(He1) ** 2))
    best = {"rank": 1, "pmi": int(beam.beam_id), "layer_sinr_lin": [float(g1[0])],
            "rank1_gain": rank1_gain, "capacity": float(np.log2(1.0 + g1[0]))}
    if H.shape[0] >= 2 and int(max_rank) >= 2:   # B2:RIC 可把 cell 的最大層數壓到 1
        W2 = gob.rank2_weights(n1, n2, beam.l, beam.m, o1, o2)
        g2 = csi_selection.layer_sinr(Hn @ W2, gamma_ref_lin)
        c2 = float(np.sum(np.log2(1.0 + g2)))
        if c2 > best["capacity"]:
            best = {"rank": 2, "pmi": int(beam.beam_id), "layer_sinr_lin": [float(x) for x in g2],
                    "rank1_gain": rank1_gain, "capacity": c2}
    return best


def _csi_for(ue_id: str, H: np.ndarray, gamma_ref_lin: float, layout, max_rank: int | None = None) -> dict:
    """RI/PMI 選擇(有快取)。鍵含通道指紋 → UE 沒動就不重算(等效於 CSI 回報週期)。"""
    max_rank = int(max_rank or _MAX_RANK)
    key = (ue_id, H.shape, round(float(np.sum(np.abs(H) ** 2)), 6),
           round(float(np.real(H.ravel()[0])), 4), round(math.log10(max(gamma_ref_lin, 1e-12)), 2), layout, max_rank)
    hit = _CSI_CACHE.get(key)
    if hit is not None:
        return hit
    sel = csi_selection.select(H, gamma_ref_lin=gamma_ref_lin, layout=layout, max_rank=max_rank)
    if len(_CSI_CACHE) >= _CSI_CACHE_MAX:
        _CSI_CACHE.clear()
    _CSI_CACHE[key] = sel
    return sel


_ANT_CACHE: dict[str, object] = {"at": 0.0, "cfg": None}


def _antenna_cfg():
    """目前的 AntennaConfig(2 秒快取;陣列設定很少變,但每 tick 每 UE 都要用)。"""
    import time as _t
    now = _t.time()
    if now - float(_ANT_CACHE["at"] or 0) > 2.0:
        try:
            from main.apps.antenna.models.antenna_config import AntennaConfig
            _ANT_CACHE["cfg"] = AntennaConfig.objects.order_by("-antenna_config_updated_at").first()
        except Exception:  # noqa: BLE001 — 沒設定就當 1×1
            _ANT_CACHE["cfg"] = None
        _ANT_CACHE["at"] = now
    return _ANT_CACHE["cfg"]


_PATH_LOOKBACK_TICKS = 60


def _synth_cached_h(ccache, tick_idx: int, ue_id: str, gains: dict) -> dict:
    """cached 模式:由路徑參數重建每個 cell 的元件層 H(n_rx_elem, n_tx_elem)。沒有路徑檔回 {}。"""
    if getattr(ccache, "paths", None) is None or not gains:
        return {}
    cfg = _antenna_cfg()
    if cfg is None:
        return {}
    from main.apps.beamforming.services.optional import path_synth
    tx = {"rows": cfg.rows, "cols": cfg.cols, "polarization": cfg.polarization,
          "vertical_spacing": cfg.vertical_spacing, "horizontal_spacing": cfg.horizontal_spacing,
          "panels_mg": getattr(cfg, "panels_mg", 1) or 1, "panels_ng": getattr(cfg, "panels_ng", 1) or 1,
          "panel_v_spacing": getattr(cfg, "panel_v_spacing", 0.0) or 0.0,
          "panel_h_spacing": getattr(cfg, "panel_h_spacing", 0.0) or 0.0}
    rx = {"rows": getattr(cfg, "ue_rows", 1) or 1, "cols": getattr(cfg, "ue_cols", 1) or 1,
          "polarization": getattr(cfg, "ue_polarization", "") or "V"}
    out = {}
    for tx_name in gains:
        hit = ccache.lookup_paths(tick_idx, ue_id, tx_name)
        # 該 tick 沒路徑(gain 已被內插補上)→ 往前找最近有路徑的 tick(最多 30 s)
        back = 1
        while hit is None and back <= _PATH_LOOKBACK_TICKS and tick_idx - back >= 0:
            hit = ccache.lookup_paths(tick_idx - back, ue_id, tx_name)
            back += 1
        if hit is None:
            continue
        A, kt, kr, orient = hit
        H = path_synth.synthesize(A, kt, kr, tx=tx, rx=rx, tx_orientation=orient, fading=True)
        if np.any(H):
            out[tx_name] = H
    return out


def _to_complex_matrix(raw: Any) -> np.ndarray:
    """Physics 回傳的 channel_matrix 元素可能是 [re,im] / {re,im} / 複數 string；統一吃成 ndarray。

    若 Sionna 給的是含 polarization 的 3D shape `(num_rx, num_pol, num_tx_ports)`，
    把 polarization 那軸 squeeze 進 num_rx：reshape 成 `(num_rx*num_pol, num_tx_ports)`。
    precoder 跟 sinr_estimator 都吃 2D `(num_rx_total, num_ports)`。
    """
    if isinstance(raw, np.ndarray) and np.iscomplexobj(raw):
        H = raw.astype(np.complex128)
    else:
        # ★ 2026-09-16:physics(path_solver_actor)把複數序列化成 **最後一軸 [re, im]**,
        #   所以 (num_rx, num_tx) 的 H 在 JSON 裡是 (num_rx, num_tx, 2) 的實數陣列。
        #   舊版用 np.vectorize 逐「純量」coerce,len(x)==2 那條分支永遠不會命中,
        #   結果 3D 被下面的 polarization 分支 reshape 成 (num_rx*num_tx, 2)——
        #   H 變成「num_rx*num_tx 根接收天線 × 2 個發射埠」。rank / PMI / 每層 SINR
        #   從 P5-3 起都是拿這個錯形狀算的。這裡先攔截標準的 [re, im] 格式。
        _plain = np.asarray(raw)
        if _plain.dtype != object and not np.iscomplexobj(_plain) and _plain.ndim >= 3 and _plain.shape[-1] == 2:
            return (_plain[..., 0] + 1j * _plain[..., 1]).astype(np.complex128)
        arr = np.array(raw, dtype=object)

        def _coerce(x):
            if isinstance(x, (int, float)):
                return complex(x, 0.0)
            if isinstance(x, complex):
                return x
            if isinstance(x, dict):
                return complex(x.get("re", x.get("real", 0.0)), x.get("im", x.get("imag", 0.0)))
            if isinstance(x, (list, tuple)) and len(x) == 2:
                return complex(x[0], x[1])
            if isinstance(x, str):
                return complex(x.replace("i", "j"))
            raise ValueError(f"cannot coerce to complex: {x!r}")

        H = np.vectorize(_coerce, otypes=[np.complex128])(arr)

    # Flatten polarization 維度進 num_rx：(num_rx, num_pol, num_tx) → (num_rx*num_pol, num_tx)
    if H.ndim == 3:
        num_rx, num_pol, num_tx = H.shape
        H = H.reshape(num_rx * num_pol, num_tx)
    elif H.ndim > 3:
        # 高維度（含時間 / path 等）保留前後兩軸，把中間 collapse
        last = H.shape[-1]
        H = H.reshape(-1, last)
    return H


def _resolve_serving(resp: PathSolverResponse, ue_id: str) -> str | None:
    """Sionna 內部 fallback: 用 resp.serving_cells 或 path_gain argmax。

    注意：呼叫端會優先用 PDU.cell_id (CU-CP 給的)，這個 fallback 只在 PDU 沒帶
    cell_id（例如舊呼叫端 / backward compat）時才會用到。回的是 gnb_name (gnb-level)。
    """
    serving = (resp.serving_cells or {}).get(ue_id)
    if serving:
        return serving
    gains = (resp.path_gain or {}).get(ue_id) or {}
    if not gains:
        return None
    return max(gains.items(), key=lambda kv: kv[1])[0]


def _cache_key(ue_id: str, ue_pos: list[float], ant_sig: tuple) -> tuple:
    return (ue_id, quantize_position(ue_pos), ant_sig)


def run(req: DlTtiRequest) -> list[CqiIndication]:
    """跑 pipeline，回傳一組 CqiIndication（已對每個 PDU 依序產生，actor 負責 dispatch 給 DU）。"""
    if not req.pdus:
        return []

    ue_ids = [p.ue_id for p in req.pdus]
    psr = build_path_solver_request(ue_ids)
    ant = psr.tx_config.antenna_array
    ant_sig = (ant.rows, ant.cols, ant.polarization, ant.pattern)

    # cache 命中 → 跳過 physics
    pos_map = {u.id: u.position for u in psr.ue_positions}
    cached: dict[str, Any] = {}
    unobserved: set[str] = set()   # physics 失敗的 UE:本 tick 不回報(見 live 分支)
    cache_hits = 0
    miss_ids: list[str] = []
    for ue_id in set(ue_ids):
        key = _cache_key(ue_id, pos_map.get(ue_id, [0, 0, 0]), ant_sig)
        hit = default_cache.get(key)
        if hit is not None:
            cached[ue_id] = hit
            cache_hits += 1
        else:
            miss_ids.append(ue_id)

    if miss_ids:
        # Phase B B.3 — cached mode: 跳過 physics_http,從 npz 查表
        ccache = get_channel_cache() if is_cached_mode() else None
        if ccache is not None:
            # tick_idx = sfn × SLOTS_PER_FRAME + slot,跟 DU tick_count 對齊
            tick_idx = int(req.sfn) * 20 + int(req.slot)
            # 新 DU 帶劇本時鐘(不受 sfn 繞回 / tick 早於劇本啟動影響)
            _scene_ms = getattr(req, "scene_sim_ms", None)
            if _scene_ms is not None:
                tick_idx = int(_scene_ms / max(1, int(getattr(ccache, "tick_ms", 500) or 500)))
            for ue_id in miss_ids:
                gains, serving_tx = ccache.lookup(tick_idx, ue_id)
                value = {
                    # 階段 C:有路徑檔就依目前天線設定重建元件層 H(與 live 同一條 MIMO 路徑)
                    "channel_matrix": _synth_cached_h(ccache, tick_idx, ue_id, gains),
                    "path_gain": gains,
                    "serving_cell": serving_tx,
                }
                cached[ue_id] = value
                default_cache.set(_cache_key(ue_id, pos_map.get(ue_id, [0, 0, 0]), ant_sig), value)
            # log every 50 ticks 不要太吵
            if tick_idx % 50 == 0:
                # 也看 lookup 第一個 UE 拿到什麼,debug cache miss
                first_ue = next(iter(miss_ids), None)
                first_val = cached.get(first_ue, {})
                pg = first_val.get("path_gain") or {}
                logger.info(
                    "dl_tti CACHED tick_idx=%d ues=%d first=%s gains_keys=%s",
                    tick_idx, len(miss_ids), first_ue, list(pg.keys())[:3],
                )
        else:
            # live mode (原本邏輯不動)
            psr.ue_positions = [u for u in psr.ue_positions if u.id in miss_ids]
            try:
                resp = physics_http.compute_paths(psr)
            except physics_http.PhysicsHttpError as exc:
                # 2026-09-15:不再退成 noise-only(SINR −100 會讓 DU 1 s 內宣告 RLF、UE 掉 IDLE 且無法自癒)。
                # 改成「本 tick 無觀測」:這批 UE 不回 CqiIndication、不進快取,下一 tick 再試。
                logger.warning("physics call failed: %s — %d UE 本 tick 無觀測(不回報、不觸發 RLF)", exc, len(miss_ids))
                unobserved.update(miss_ids)
                resp = None
            _scene_ms = getattr(req, "scene_sim_ms", None)
            for ue_id in (miss_ids if resp is not None else []):
                value = {
                    "channel_matrix": (resp.channel_matrix or {}).get(ue_id, {}),
                    # 光追雜訊平滑(cached 在載入 cache 時做,live 在這裡做)
                    "path_gain": live_smoothing.smooth(ue_id, (resp.path_gain or {}).get(ue_id, {}),
                                                       None if _scene_ms is None else _scene_ms / 1000.0),
                    "serving_cell": _resolve_serving(resp, ue_id),
                }
                cached[ue_id] = value
                default_cache.set(_cache_key(ue_id, pos_map.get(ue_id, [0, 0, 0]), ant_sig), value)

    logger.debug("dl_tti sfn=%d slot=%d pdus=%d cache_hit=%d/%d",
                 req.sfn, req.slot, len(req.pdus), cache_hits, len(set(ue_ids)))

    # AK7: Sionna path_gain 改 per-tx (cell-level), CU/DU 也是 cell-level → 直接對應
    # cell_to_tx 把 sim cell_name (e.g. gnb4_c0) 對到 Sionna tx_name (gnb4#0)
    gnb_to_cell = _build_gnb_to_cell_map()       # gnb_id → 第一個 cell.name (legacy fallback)
    cell_to_gnb = _build_cell_to_gnb_map()       # cell.name → gnb_id (legacy fallback)
    cell_to_tx  = _build_cell_to_tx_map()        # cell.name → tx_name (主 path)
    # AK8: 每 cell 的 TX 功率 — Dashboard 透過 update_cells 推進來，這裡用來算 RSRP，
    # 一次撈起來給整個 batch 用，不在 inner loop 打 DB。
    cell_to_power = _build_cell_to_power_map()   # cell.name → power_dbm
    cell_to_freq = _build_cell_to_freq_map()     # cell.name → (freq_ghz, bw_mhz),頻率重疊干擾用

    out: list[CqiIndication] = []
    ul_ctx: dict[str, dict] = {}   # P6:給第二趟算上行 SINR 用
    for pdu in req.pdus:
        if pdu.ue_id in unobserved:
            continue
        bundle = cached.get(pdu.ue_id) or {}
        path_gain_dict = bundle.get("path_gain") or {}
        channel_dict = bundle.get("channel_matrix") or {}

        # Serving cell 決策 (對齊真實 O-RAN: CU-CP 是 source of truth):
        #   1. 優先用 pdu.cell_id（DU 從 _ue_registry 帶下來，根源是 CU-CP UeContext.serving_cell）
        #   2. fallback: Sionna argmax (舊行為，給 backward compat / pdu 沒帶時用)
        # 注意 cell_id 是 cell-level (e.g., gnb4_c0)，但 Sionna path_gain 是 gnb-level (gnb4)。
        # 用 cell_to_gnb map 翻譯後查 path_gain。
        serving_cell_id = (pdu.cell_id or "").strip()
        if serving_cell_id:
            # AK7: 主 path 用 cell→tx 對映, 拿 per-cell path_gain (不再 per-gnb max)
            serving_tx  = cell_to_tx.get(serving_cell_id)
            serving_gnb = cell_to_gnb.get(serving_cell_id, serving_cell_id)
            serving_label = serving_cell_id   # CqiIndication 給 cell-level
        else:
            serving_tx  = None
            serving_gnb = bundle.get("serving_cell")  # Sionna fallback (tx_name)
            serving_label = gnb_to_cell.get(serving_gnb) or ""

        # AK7: 優先 tx_name lookup (per-cell); 沒 hit 退 gnb_name (backward compat)
        H_raw = None
        path_gain_linear = None
        if serving_tx:
            path_gain_linear = path_gain_dict.get(serving_tx)
            H_raw = channel_dict.get(serving_tx)
        if path_gain_linear is None and serving_gnb:
            path_gain_linear = path_gain_dict.get(serving_gnb)
            if H_raw is None:
                H_raw = channel_dict.get(serving_gnb)
        # AI3 final fallback: argmax (= Sionna 自己 serving_cells 判定)
        if path_gain_linear is None and path_gain_dict:
            best_key = max(path_gain_dict, key=lambda k: path_gain_dict.get(k, 0.0))
            path_gain_linear = path_gain_dict.get(best_key)
            if H_raw is None:
                H_raw = channel_dict.get(best_key)
        # AK8: 用 per-cell power 算 RSRP。serving_label 是 sim cell_name（如 gnb4_c0）。
        rsrp_dbm = _path_gain_to_rsrp_dbm(
            path_gain_linear,
            cell_power_dbm=cell_to_power.get(serving_label),
        )

        # Neighbor cell measurements — Sionna path_gain dict 現在 key 是 tx_name
        # (e.g. "gnb4#0", "gnb4#1"). 排除 serving_tx (跟 serving 同 cell 不算 neighbor).
        # 建反向表 tx_name → sim cell_name 供 A3 用 cell-level 名字.
        # AK7: 同 gNB 不同 sectored cell 現在都是 neighbor candidate, 不再過早 collapse.
        neighbors_list: list[dict] = []
        tx_to_cell = {v: k for k, v in cell_to_tx.items()}   # gnb4#0 → gnb4_c0
        for key, pg in path_gain_dict.items():
            if key == serving_tx or key == serving_gnb:
                continue
            if not isinstance(pg, (int, float)) or pg <= 0:
                continue
            # AK8: 先 resolve cell_id 再算 RSRP，這樣可以用該 neighbor cell 自己的 power_dbm
            # tx_name (gnb4#0) → sim cell_id (gnb4_c0); 退 gnb_name → first cell of that gnb
            cell_id_for_a3 = tx_to_cell.get(key) or gnb_to_cell.get(key)
            if not cell_id_for_a3:
                continue
            neigh_rsrp = _path_gain_to_rsrp_dbm(
                pg,
                cell_power_dbm=cell_to_power.get(cell_id_for_a3),
            )
            if neigh_rsrp <= _NEIGHBOR_RSRP_FLOOR_DBM:
                continue
            neighbors_list.append({
                "cell_id": cell_id_for_a3,
                "rsrp_dbm": neigh_rsrp,
                "rsrq_db": 0.0,
            })

        # SINR 統一算法(cached + live 同源):從 path_gain_dict 算真實 inter-cell
        # interference。task #91 — 之前 cached 跟 live 兩條公式各自有 bug(cached
        # 漏 35 dB per-RE 單位,live 用 H matrix 但忽略其他 cell 干擾),改成兩個
        # 都走同一個 helper,cell center 跟 edge SINR 自然不同。
        sinr_db = _compute_sinr_db_with_real_interference(
            path_gain_dict=path_gain_dict,
            serving_tx=serving_tx,
            serving_gnb=serving_gnb,
            tx_to_cell=tx_to_cell,
            gnb_to_cell=gnb_to_cell,
            cell_to_power=cell_to_power,
            cell_to_freq=cell_to_freq,
            cell_dl_load=getattr(req, "cell_dl_load", None),
        )
        # 額外保留的 env penalty(0 default),想模擬 multipath fade margin 才動
        if sinr_db != -float("inf"):
            sinr_db -= _SINR_INTERFERENCE_PENALTY_DB

        # RI / PMI:A2(2026-09-16)。以前 DU 固定送 layers=1 / pmi=0,RU 只拿未預編碼的 H
        # 做 SVD 猜 rank,預編碼其實沒在動。現在 RU 代 UE 做 CSI 選擇(TS 38.214 §5.2.2):
        # 對候選 (rank, PMI) 算 MMSE 每層 SINR,挑容量最大的回報,DU 下一輪就照這個下 PDU。
        sinr_per_layer: list[float] = []
        rank_pmi = int(pdu.pmi)
        beam_id: int | None = None
        beam_top: list = []
        array_gain_db = 0.0
        if H_raw is None:
            rank = 1
        else:
            try:
                H_elem = _to_complex_matrix(H_raw)
                # 三層天線(2026-09-16):physics 回的是**元件層**,先經 virtualization + 埠映射
                # 壓到**埠層**,PMI / RI 才是 TS 38.214 講的那個埠數。舊 1×1 設定下 chain = 單位矩陣。
                # B2:per-cell 的 RIC 控制值(電子下傾疊在 preset 之上)
                _bc = _beam_ctrl(serving_label or "")
                _etilt = (float(getattr(_antenna_cfg(), "electrical_tilt_deg", 0.0) or 0.0)
                          + float(_bc["etilt"])) if _bc["etilt"] else None
                # 2026-09-17:節能關 TXRU / 波束加窗 —— 元件層權重,在虛擬化之前乘上
                _cfg = _antenna_cfg()
                if _cfg is not None and (_bc.get("trx_ratio", 1.0) < 0.999 or _bc.get("taper")):
                    _ew = virtualization.element_weights(
                        rows=_cfg.rows, cols=_cfg.cols, polarization=_cfg.polarization,
                        panels_mg=getattr(_cfg, "panels_mg", 1) or 1, panels_ng=getattr(_cfg, "panels_ng", 1) or 1,
                        trx_active_ratio=_bc.get("trx_ratio", 1.0), taper=_bc.get("taper", ""))
                    if _ew is not None and H_elem.ndim == 2 and H_elem.shape[1] == _ew.size:
                        H_elem = H_elem * _ew[None, :]
                H, _chain = array_chain.to_ports(H_elem, _cfg, etilt=_etilt)
                _layout = _chain.get("layout")
                if H.size and H.shape[1] > 1 and sinr_db != -float("inf"):
                    _g_ref = _apply_evm_lin(10.0 ** (float(sinr_db) / 10.0))   # 選 rank 也要看失真上限,否則近場永遠選滿層
                    # B1(2026-09-16):GoB。Cat A 也算,只是拿來當 KPI(O-RAN WG1 §4.6.4.1 要每波束 RSRP);
                    # Cat B + predefined-beam 則直接用 beamId 對應的權重做預編碼(O-DU 只送 beamId)。
                    _beams = gob.active_subset(gob.for_config(_antenna_cfg(), _chain), _bc["beams"])
                    if _beams:
                        _bsel = gob.select(H, _beams, top_k=8)   # 階段 D:DU 用前 8 名估 MU 波束互漏
                        beam_id = _bsel.get("beam_id")
                        beam_top = _bsel.get("top") or []
                    if _chain.get("ru_category") == "B" and _beams and beam_id is not None:
                        # 注意:_beams 可能已被 active_subset 篩過,不能用 beam_id 當索引
                        _b = next((b for b in _beams if b.beam_id == beam_id), _beams[0])
                        _sel = _cat_b_select(H, _b, _g_ref, _layout, max_rank=(_bc["max_layers"] or _MAX_RANK))
                    else:
                        _sel = _csi_for(pdu.ue_id, H, _g_ref, _layout, max_rank=(_bc["max_layers"] or _MAX_RANK))
                    rank = int(_sel["rank"])
                    rank_pmi = int(_sel["pmi"])
                    # 寬頻 SINR 改由「最佳單層預編碼」的陣列增益推導 → 天線變大 SINR 才會變好
                    array_gain_db = 10.0 * math.log10(max(float(_sel["rank1_gain"]), 1e-12))
                    # Cat B 每波束功率(WG1 §4.6.3):RIC 壓低某道波束 → 用它的 UE 訊號跟著降
                    _pwr = 0.0
                    if _chain.get("ru_category") == "B" and beam_id is not None:
                        _pwr = float((_bc.get("beam_pwr") or {}).get(str(beam_id), 0.0))
                    array_gain_db += _pwr
                    sinr_db = float(sinr_db) + array_gain_db
                    sinr_per_layer = [10.0 * math.log10(max(_apply_evm_lin(g * 10.0 ** (_pwr / 10.0)), 1e-12))
                                      for g in _sel["layer_sinr_lin"]]
                else:
                    rank = 1
            except (codebook.CodebookError, codebook_type1.CodebookError, ValueError) as exc:
                logger.warning("codebook lookup failed for ue=%s: %s", pdu.ue_id, exc)
                rank = 1

        if sinr_db != -float("inf"):
            sinr_db = _apply_evm_db(float(sinr_db))   # 陣列增益之後再壓一次(失真也在同一條路徑上)
        cqi = sinr_estimator.sinr_to_cqi(sinr_db) if sinr_db != -float("inf") else 0

        logger.debug(
            "DL TTI ue=%s serving_cell=%s (gnb=%s, src=%s) path_gain=%s → rsrp=%.1f dBm, sinr=%.1f dB",
            pdu.ue_id, serving_label, serving_gnb,
            "CU-PDU" if serving_cell_id else "Sionna-argmax",
            path_gain_linear, rsrp_dbm,
            float(sinr_db) if sinr_db != -float("inf") else -100.0,
        )

        ul_ctx[pdu.ue_id] = {"serving": serving_label, "serving_tx": serving_tx or serving_gnb, "pg_serv": path_gain_linear, "pg": path_gain_dict}
        out.append(CqiIndication(
            ue_id=pdu.ue_id,
            sinr_db=float(sinr_db) if sinr_db != -float("inf") else -100.0,
            cqi=int(cqi),
            rank=int(rank),
            sinr_per_layer_db=[round(v, 2) for v in sinr_per_layer],
            pmi=int(rank_pmi),   # A2:RU 代 UE 選的 PMI,DU 下一輪照這個下 PDU
            beam_id=beam_id, beam_rsrp_top=beam_top,   # B1:GoB 波束(O-RAN WG1 每波束 KPI)
            array_gain_db=round(float(array_gain_db), 2),
            rsrp_dbm=rsrp_dbm,
            serving_cell=serving_label,
            neighbors=neighbors_list,
        ))
    # P6:上行 SINR(整批一起算,干擾要看別的 UE)
    try:
        ul = _compute_ul_sinr_db(ul_ctx, cell_to_freq, _read_inter_freq(), _build_cell_to_ul_load_map(getattr(req, "cell_ul_load", None)))
        for ind in out:
            if ind.ue_id in ul:
                ind.ul_sinr_db = round(ul[ind.ue_id], 2)
    except Exception as exc:  # noqa: BLE001 — UL 算失敗不能拖垮 DL
        logger.warning("ul sinr pass failed: %s", exc)

    return out
