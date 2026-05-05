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
            return error_response("ue_positions required", http_status=400)

        # 轉成 sionna_engine 期望的格式
        sionna_input = []
        for ue in ue_positions:
            sionna_input.append({
                "id": ue["id"],
                "position": ue["position"],
                "velocity": ue.get("velocity", [0.0, 0.0, 0.0]),
            })

        # tx_config 跟 rx_config 目前 Physics_sim 內 sionna scene 已經 baked-in（在 init_scene 階段配好）
        # 未來要支援動態切換 antenna config 再從 body 讀
        try:
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
