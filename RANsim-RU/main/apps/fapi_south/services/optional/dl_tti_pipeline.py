"""DL TTI pipeline — Physics → Beamforming → SINR/CQI → DU callback。

對應 OAI: nr-ru.c::ru_thread() 收到 nFAPI DL request 後的處理鏈，
但這裡不真做 IFFT/RF；只算 UE-side SINR 量測。
"""
from __future__ import annotations

from typing import Any

import numpy as np
from django.conf import settings
from ran_sim_protocol.fapi import CqiIndication, DlTtiRequest
from ran_sim_protocol.physics import PathSolverResponse

from main.apps.beamforming.services.optional import codebook, precoder, sinr_estimator
from main.apps.physics_client.services.optional import physics_http
from main.apps.physics_client.services.optional.channel_cache import default_cache, quantize_position
from main.apps.physics_client.services.optional.payload_builder import build_path_solver_request
from main.utils.env_loader import get_float
from main.utils.logger import get_logger


logger = get_logger(__name__)


_NOISE_FLOOR_DBM = get_float("RU_NOISE_FLOOR_DBM", default=-95.0)
_TX_POWER_DBM = get_float("RU_TX_POWER_DBM", default=43.0)  # 典型 macrocell 20W = 43 dBm
_ANTENNA_GAIN_DBI = get_float("RU_ANTENNA_GAIN_DBI", default=14.0)  # TR 38.901 antenna 預設
_NEIGHBOR_RSRP_FLOOR_DBM = get_float("RU_NEIGHBOR_RSRP_FLOOR_DBM", default=-120.0)
"""比 -120 dBm 弱的 neighbor 不報，避免 A3 evaluator 看一堆 noise。"""

# AC1: scene calibration loss — sim Brownstone 場景比真實 urban 環境小, Sionna ray-tracing
# 只算了 free-space + scene geometry (建物反射/繞射), 沒模擬以下真機常見額外損耗:
#   • building penetration (UE 在室內, 18-25 dB)
#   • body loss / clutter (UE 拿手裡或包裡, 5-10 dB)
#   • shadowing fade (lognormal, ~8 dB σ)
#   • foliage / weather attenuation
# 對映 3GPP TR 38.901 §7.4.3.1 Outdoor-to-Indoor (O2I) loss + shadowing.
# 加總約 50 dB, 把 sim RSRP 從 ~-15 dBm 校正到真機典型 -65~-95 dBm 範圍.
_SCENE_CALIBRATION_LOSS_DB = get_float("RU_SCENE_CALIBRATION_LOSS_DB", default=50.0)
"""場景外建物穿透 + body loss + shadowing 額外損耗 (Brownstone 場景沒模擬到的)."""

# SINR 同樣需要校正: sim 場景算出來太乾淨 (47-60 dB), 真機常見 5-25 dB.
# 干擾沒模擬足 (其他 cell 的 inter-cell interference 沒進 SINR 算式).
_SINR_INTERFERENCE_PENALTY_DB = get_float("RU_SINR_INTERFERENCE_PENALTY_DB", default=20.0)
"""inter-cell interference + multipath fading penalty (sim 沒完整模擬)."""


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
    """cell_name → gnb_name 反向對照。CU 給的 PDU.cell_id 是 cell-level (gnb4_c0),
    Sionna path_gain 是 gnb-level (gnb4)，要這個 map 才能查到對應 channel。"""
    try:
        from main.apps.antenna.models.cell import Cell
        return {c.name: c.gnb_id for c in Cell.objects.all() if c.gnb_id}
    except Exception:
        return {}


def _path_gain_to_rsrp_dbm(path_gain_linear: float) -> float:
    """從 Sionna 回的 linear path_gain 算 RSRP (dBm)。

    RSRP = TX_power_dBm + antenna_gain_dBi + 10*log10(path_gain_linear)
                       - SCENE_CALIBRATION_LOSS_DB  (sim 場景額外損耗校正)

    path_gain_linear 是 Sionna 算出的 "received power / transmit power"（無量綱），
    所以 10*log10(it) = path_gain_dB（負值，因為衰減）。

    SCENE_CALIBRATION_LOSS_DB 補償 sim Brownstone 場景沒模擬到的 building
    penetration + body loss + shadowing (真機這些加總 30-50 dB 額外損耗).
    沒這個校正 sim 算出來 RSRP -15 dBm 會撞 3GPP encoding 上限 -31 dBm → 127.
    """
    if path_gain_linear is None or path_gain_linear <= 0:
        return -200.0  # 沒訊號 sentinel
    path_gain_db = 10.0 * np.log10(float(path_gain_linear))
    return _TX_POWER_DBM + _ANTENNA_GAIN_DBI + path_gain_db - _SCENE_CALIBRATION_LOSS_DB


def _to_complex_matrix(raw: Any) -> np.ndarray:
    """Physics 回傳的 channel_matrix 元素可能是 [re,im] / {re,im} / 複數 string；統一吃成 ndarray。

    若 Sionna 給的是含 polarization 的 3D shape `(num_rx, num_pol, num_tx_ports)`，
    把 polarization 那軸 squeeze 進 num_rx：reshape 成 `(num_rx*num_pol, num_tx_ports)`。
    precoder 跟 sinr_estimator 都吃 2D `(num_rx_total, num_ports)`。
    """
    if isinstance(raw, np.ndarray):
        H = raw.astype(np.complex128)
    else:
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
        # 只對 miss 的 UE 重新打 Physics（ue_positions 可裁切）
        psr.ue_positions = [u for u in psr.ue_positions if u.id in miss_ids]
        try:
            resp = physics_http.compute_paths(psr)
        except physics_http.PhysicsHttpError as exc:
            logger.warning("physics call failed: %s — fall back to noise-only SINR", exc)
            resp = PathSolverResponse(channel_matrix={}, path_gain={}, serving_cells={})
        for ue_id in miss_ids:
            value = {
                "channel_matrix": (resp.channel_matrix or {}).get(ue_id, {}),
                "path_gain": (resp.path_gain or {}).get(ue_id, {}),
                "serving_cell": _resolve_serving(resp, ue_id),
            }
            cached[ue_id] = value
            default_cache.set(_cache_key(ue_id, pos_map.get(ue_id, [0, 0, 0]), ant_sig), value)

    logger.debug("dl_tti sfn=%d slot=%d pdus=%d cache_hit=%d/%d",
                 req.sfn, req.slot, len(req.pdus), cache_hits, len(set(ue_ids)))

    # 兩個方向的對照表 — 因為 Sionna 是 gnb-level，CU/DU 用 cell-level
    gnb_to_cell = _build_gnb_to_cell_map()       # gnb_id → 第一個 cell.name
    cell_to_gnb = _build_cell_to_gnb_map()       # cell.name → gnb_id

    out: list[CqiIndication] = []
    for pdu in req.pdus:
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
            serving_gnb = cell_to_gnb.get(serving_cell_id, serving_cell_id)
            serving_label = serving_cell_id   # CqiIndication 給 cell-level
        else:
            serving_gnb = bundle.get("serving_cell")  # Sionna fallback (gnb-level)
            # 同 neighbors 邏輯: Sionna gnb_name 沒對應到 sim cell 時 — 不要 leak 進 serving_label,
            # 留空字串 (DU 端拿空 serving_cell 已有 fallback 行為), 避免污染 UE Context.
            serving_label = gnb_to_cell.get(serving_gnb) or ""

        H_raw = channel_dict.get(serving_gnb) if serving_gnb else None
        path_gain_linear = path_gain_dict.get(serving_gnb) if serving_gnb else None
        # AI3 fallback: sim CellConfig.gnb_id (e.g., "gnb4") 跟 Sionna scene gNB
        # 名稱 (e.g., "gNB_Macro_NW") 不直接對應, path_gain_dict.get(serving_gnb)
        # 常 None → RSRP -200 sentinel. 回 argmax (最強) path_gain 當 fallback,
        # 對應 Sionna 自己 serving_cells 判定 (= UE 連到的最強 cell).
        if path_gain_linear is None and path_gain_dict:
            best_gnb = max(path_gain_dict, key=lambda k: path_gain_dict.get(k, 0.0))
            path_gain_linear = path_gain_dict.get(best_gnb)
            if H_raw is None:
                H_raw = channel_dict.get(best_gnb)
        rsrp_dbm = _path_gain_to_rsrp_dbm(path_gain_linear)

        # Neighbor cell measurements — 排除 serving_gnb (跟 serving 同 gNB 的不算 neighbor)
        neighbors_list: list[dict] = []
        for gnb_name, pg in path_gain_dict.items():
            if gnb_name == serving_gnb:
                continue
            if not isinstance(pg, (int, float)) or pg <= 0:
                continue
            neigh_rsrp = _path_gain_to_rsrp_dbm(pg)
            if neigh_rsrp <= _NEIGHBOR_RSRP_FLOOR_DBM:
                continue
            # Sionna scene gNB 名 (e.g., gNB_Macro_NW) 跟 sim CellConfig 不相通時,
            # gnb_to_cell.get() 會 None — 之前 fallback 把 gnb_name 當 cell_id leak
            # 進 A3 evaluator, 觸發 phantom HO 把 UE.serving_cell 寫成不存在的 cell.
            # 修: 沒對應到 sim 內部 cell 直接 drop, 不污染 A3.
            cell_id_for_a3 = gnb_to_cell.get(gnb_name)
            if not cell_id_for_a3:
                continue
            neighbors_list.append({
                "cell_id": cell_id_for_a3,
                "rsrp_dbm": neigh_rsrp,
                "rsrq_db": 0.0,    # 沒實作 RSRQ 計算，A3 不依賴
            })

        if H_raw is None:
            # 沒 channel — 給最差量測（SINR ≈ noise floor）
            sinr_db = -float("inf")
            rank = 1
            cqi = 0
        else:
            H = _to_complex_matrix(H_raw)
            num_ports = H.shape[1]
            try:
                H_eff = precoder.apply_pmi(H, pmi=pdu.pmi, layers=pdu.layers)
                sinr_db = sinr_estimator.estimate_sinr(H_eff, _NOISE_FLOOR_DBM)
                # AC1: 補償 sim 沒模擬的 inter-cell interference + multipath fading
                sinr_db -= _SINR_INTERFERENCE_PENALTY_DB
                rank = sinr_estimator.estimate_rank(H_eff)
                cqi = sinr_estimator.sinr_to_cqi(sinr_db)
            except codebook.CodebookError as exc:
                logger.warning("codebook lookup failed for ue=%s: %s", pdu.ue_id, exc)
                sinr_db, rank, cqi = -float("inf"), 1, 0

        logger.debug(
            "DL TTI ue=%s serving_cell=%s (gnb=%s, src=%s) path_gain=%s → rsrp=%.1f dBm, sinr=%.1f dB",
            pdu.ue_id, serving_label, serving_gnb,
            "CU-PDU" if serving_cell_id else "Sionna-argmax",
            path_gain_linear, rsrp_dbm,
            float(sinr_db) if sinr_db != -float("inf") else -100.0,
        )

        out.append(CqiIndication(
            ue_id=pdu.ue_id,
            sinr_db=float(sinr_db) if sinr_db != -float("inf") else -100.0,
            cqi=int(cqi),
            rank=int(rank),
            pmi=int(pdu.pmi),
            rsrp_dbm=rsrp_dbm,
            serving_cell=serving_label,
            neighbors=neighbors_list,
        ))
    return out
