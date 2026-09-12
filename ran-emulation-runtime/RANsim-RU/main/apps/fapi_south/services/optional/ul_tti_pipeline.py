"""UL TTI pipeline — 對應 DL pipeline，但回 CrcIndication（HARQ 用）。

簡化：以 UL SINR 是否高過門檻決定 success。
不真做 LDPC decode（rule §11 不在範圍）。
"""
from __future__ import annotations

from ran_sim_protocol.fapi import CrcIndication, UlTtiRequest

from main.apps.fapi_south.services.optional.dl_tti_pipeline import (
    _NOISE_FLOOR_DBM,
    _cache_key,
    _resolve_serving,
    _to_complex_matrix,
)
from main.apps.beamforming.services.optional import precoder, sinr_estimator
from main.apps.physics_client.services.optional import physics_http
from main.apps.physics_client.services.optional.channel_cache import default_cache
from main.apps.physics_client.services.optional.payload_builder import build_path_solver_request
from main.utils.logger import get_logger


logger = get_logger(__name__)


_UL_SINR_DB_THRESHOLD = -2.0  # 約等於 CQI 1 的下緣


def run(req: UlTtiRequest) -> list[CrcIndication]:
    if not req.pdus:
        return []

    ue_ids = [p.ue_id for p in req.pdus]
    psr = build_path_solver_request(ue_ids)
    ant = psr.tx_config.antenna_array
    ant_sig = (ant.rows, ant.cols, ant.polarization, ant.pattern)
    pos_map = {u.id: u.position for u in psr.ue_positions}

    miss_ids = []
    cached = {}
    for ue_id in set(ue_ids):
        key = _cache_key(ue_id, pos_map.get(ue_id, [0, 0, 0]), ant_sig)
        hit = default_cache.get(key)
        if hit is not None:
            cached[ue_id] = hit
        else:
            miss_ids.append(ue_id)

    if miss_ids:
        psr.ue_positions = [u for u in psr.ue_positions if u.id in miss_ids]
        try:
            resp = physics_http.compute_paths(psr)
        except physics_http.PhysicsHttpError as exc:
            logger.warning("UL physics call failed: %s", exc)
            resp = None

        for ue_id in miss_ids:
            if resp is None:
                cached[ue_id] = None
                continue
            bundle = {
                "channel_matrix": (resp.channel_matrix or {}).get(ue_id, {}),
                "serving_cell": _resolve_serving(resp, ue_id),
            }
            cached[ue_id] = bundle
            default_cache.set(_cache_key(ue_id, pos_map.get(ue_id, [0, 0, 0]), ant_sig), bundle)

    out: list[CrcIndication] = []
    for pdu in req.pdus:
        bundle = cached.get(pdu.ue_id)
        if not bundle:
            out.append(CrcIndication(ue_id=pdu.ue_id, harq_pid=pdu.harq_pid, success=False))
            continue
        serving = bundle.get("serving_cell")
        H_raw = (bundle.get("channel_matrix") or {}).get(serving) if serving else None
        if H_raw is None:
            out.append(CrcIndication(ue_id=pdu.ue_id, harq_pid=pdu.harq_pid, success=False))
            continue

        H = _to_complex_matrix(H_raw)
        try:
            # UL：UE 端無 PMI，先用 PMI 0 當 reference 算個 effective channel
            H_eff = precoder.apply_pmi(H, pmi=0, layers=max(1, pdu.layers))
        except Exception:  # noqa: BLE001
            out.append(CrcIndication(ue_id=pdu.ue_id, harq_pid=pdu.harq_pid, success=False))
            continue

        sinr_db = sinr_estimator.estimate_sinr(H_eff, _NOISE_FLOOR_DBM)
        out.append(CrcIndication(
            ue_id=pdu.ue_id,
            harq_pid=pdu.harq_pid,
            success=bool(sinr_db >= _UL_SINR_DB_THRESHOLD),  # cast numpy.bool_ → Python bool
        ))
    return out
