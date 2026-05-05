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
    """選 serving cell：優先用 resp.serving_cells；fallback 取 path_gain 最大那個。"""
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

    out: list[CqiIndication] = []
    for pdu in req.pdus:
        bundle = cached.get(pdu.ue_id) or {}
        serving = bundle.get("serving_cell")
        H_raw = (bundle.get("channel_matrix") or {}).get(serving) if serving else None

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
                rank = sinr_estimator.estimate_rank(H_eff)
                cqi = sinr_estimator.sinr_to_cqi(sinr_db)
            except codebook.CodebookError as exc:
                logger.warning("codebook lookup failed for ue=%s: %s", pdu.ue_id, exc)
                sinr_db, rank, cqi = -float("inf"), 1, 0

        out.append(CqiIndication(
            ue_id=pdu.ue_id,
            sinr_db=float(sinr_db) if sinr_db != -float("inf") else -100.0,
            cqi=int(cqi),
            rank=int(rank),
            pmi=int(pdu.pmi),
        ))
    return out
