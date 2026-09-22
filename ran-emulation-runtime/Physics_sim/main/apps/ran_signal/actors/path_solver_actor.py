"""PathSolverActor — RU 呼叫的物理 ray tracing endpoint。

對應 ran-sim-protocol/physics.py 的 PathSolverRequest / PathSolverResponse。

Endpoint:
    POST /api/v0.1/Physics/RanCalc/PathSolver/compute
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.ran_signal.services.business.sionna_operations import (
    SionnaBusinessService,
)
from main.utils.env_loader import get_bool
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


logger = get_logger(__name__)


def _serialize_h(matrix: Any) -> list:
    """numpy complex array → nested list of [re, im]，方便 JSON 傳輸。"""
    if matrix is None:
        return []
    arr = np.asarray(matrix)
    if arr.dtype == object:
        # 已經是 nested list-like 結構，遞迴每元素
        return _walk(arr.tolist())
    if np.iscomplexobj(arr):
        out = np.empty(arr.shape + (2,), dtype=float)
        out[..., 0] = arr.real
        out[..., 1] = arr.imag
        return out.tolist()
    # real-only → wrap with 0 imag
    return arr.tolist()


def _walk(x):
    if isinstance(x, complex):
        return [x.real, x.imag]
    if isinstance(x, list):
        return [_walk(i) for i in x]
    return x


_ANTENNA_FROM_REQUEST = get_bool("PHY_ANTENNA_FROM_REQUEST", default=True)


def _apply_request_antenna(body: dict) -> None:
    tx = body.get("tx_config") or {}
    ta = tx.get("antenna_array") or {}
    if not ta:
        return
    ra = (body.get("rx_config") or {}).get("antenna_array") or {}
    antenna_cfg = {
        "gnb_antenna_pattern": ta.get("pattern", "tr38901"), "gnb_polarization": ta.get("polarization", "V"),
        "gnb_array_rows": int(ta.get("rows", 1)), "gnb_array_cols": int(ta.get("cols", 1)),
        "gnb_v_spacing": float(ta.get("vertical_spacing", 0.5)), "gnb_h_spacing": float(ta.get("horizontal_spacing", 0.5)),
        "ue_antenna_pattern": ra.get("pattern", "dipole"), "ue_polarization": ra.get("polarization", "V"),
        "ue_array_rows": int(ra.get("rows", 1)), "ue_array_cols": int(ra.get("cols", 1)),
        "ue_v_spacing": float(ra.get("vertical_spacing", 0.5)), "ue_h_spacing": float(ra.get("horizontal_spacing", 0.5)),
    }
    tilts = {f"{g.get('name')}#{c.get('pci')}": float(c.get("tilt_deg", 0) or 0) for g in tx.get("gnbs") or [] for c in g.get("cells") or []}
    # 2026-09-22:方位也要比。Transmitter 的 orientation 是建場景時定的,
    # 請求帶了新方位卻不重建的話,執行期改天線完全不會影響 ray tracing。
    azimuths = {f"{g.get('name')}#{c.get('pci')}": float(c.get("azimuth_deg", 0) or 0) for g in tx.get("gnbs") or [] for c in g.get("cells") or []}
    if SionnaBusinessService.ensure_antenna(antenna_cfg, tilts, azimuths):
        logger.info("antenna config applied from request: gnb %sx%s %s/%s ue %sx%s %s", antenna_cfg["gnb_array_rows"], antenna_cfg["gnb_array_cols"], antenna_cfg["gnb_antenna_pattern"], antenna_cfg["gnb_polarization"], antenna_cfg["ue_array_rows"], antenna_cfg["ue_array_cols"], antenna_cfg["ue_antenna_pattern"])


class PathSolverActor:
    """RU → Physics 的 ray tracing 入口。"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def compute(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), http_status=400)

        ue_positions = body.get("ue_positions") or []
        if not isinstance(ue_positions, list) or not ue_positions:
            # AG2 fix: 空 ue_positions 不再 400.
            # RU UePosition DB 可能還沒被 UE container 同步 (cold start race),
            # 直接 graceful degrade — 回空 channel, RU 端 noise-only fall-back 已實作.
            # 真治本 (UE → RU position sync trace) 在 backlog AG3.
            logger.info(
                "Empty ue_positions — returning empty channel (RU will use noise-only SINR)",
            )
            return success_response(
                {"channel_matrix": {}, "path_gain": {}, "serving_cells": {}},
                "no UE — empty channel",
            )

        # 轉成 sionna_engine 期望的格式
        sionna_input = []
        for ue in ue_positions:
            sionna_input.append({
                "id": ue["id"],
                "position": ue["position"],
                "velocity": ue.get("velocity", [0.0, 0.0, 0.0]),
            })

        # P5(2026-09-13):tx_config / rx_config 的天線陣列 + 每 cell tilt 現在會被讀;跟 scene 目前不同就重建 engine。
        # 陣列是 scene-global(Sionna 限制),tilt 是 per-cell。env PHY_ANTENNA_FROM_REQUEST=off 可關回 baked-in。
        try:
            if _ANTENNA_FROM_REQUEST:
                _apply_request_antenna(body)
            cir_result = SionnaBusinessService.compute_paths(ue_positions=sionna_input)
        except Exception as exc:
            logger.exception("Sionna compute_paths failed")
            return error_response("compute failed", str(exc), http_status=500)

        # serialize channel_matrix（複數 ndarray → nested list）
        ch = cir_result.get("channel_matrix") or {}
        channel_matrix_out: dict = {}
        for ue_id, gnb_map in ch.items():
            channel_matrix_out[ue_id] = {
                gname: _serialize_h(H) for gname, H in gnb_map.items()
            }

        return success_response({
            "channel_matrix": channel_matrix_out,
            "path_gain": cir_result.get("path_gain_linear", {}),
            "serving_cells": cir_result.get("serving_cells", {}),
        }, "OK")
