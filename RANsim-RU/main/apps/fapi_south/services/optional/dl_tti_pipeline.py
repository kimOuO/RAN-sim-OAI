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
# Fallback TX power 給沒 Cell DB record 的極早期啟動階段；正常運行讀 Cell.power_dbm。
_TX_POWER_DBM_FALLBACK = get_float("RU_TX_POWER_DBM", default=43.0)
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
_SCENE_CALIBRATION_LOSS_DB = get_float("RU_SCENE_CALIBRATION_LOSS_DB", default=36.0)
"""真實場景額外損耗 (Brownstone 場景沒模擬到的 O2I + body + shadowing)."""

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

    # AK7: Sionna path_gain 改 per-tx (cell-level), CU/DU 也是 cell-level → 直接對應
    # cell_to_tx 把 sim cell_name (e.g. gnb4_c0) 對到 Sionna tx_name (gnb4#0)
    gnb_to_cell = _build_gnb_to_cell_map()       # gnb_id → 第一個 cell.name (legacy fallback)
    cell_to_gnb = _build_cell_to_gnb_map()       # cell.name → gnb_id (legacy fallback)
    cell_to_tx  = _build_cell_to_tx_map()        # cell.name → tx_name (主 path)
    # AK8: 每 cell 的 TX 功率 — Dashboard 透過 update_cells 推進來，這裡用來算 RSRP，
    # 一次撈起來給整個 batch 用，不在 inner loop 打 DB。
    cell_to_power = _build_cell_to_power_map()   # cell.name → power_dbm

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
