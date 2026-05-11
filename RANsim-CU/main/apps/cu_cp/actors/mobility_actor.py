"""Mobility (A3) runtime config endpoints — Dashboard 可控 A3 開關 + 參數.

AK11: GET state, POST set. 不需要 CU restart, runtime 生效.
A3HandoverCalculation 每次 evaluate() 都從 store 讀, 改完即時下次 measurement_report 套用.
"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.services.optional.mobility.a3_handover_calculation import (
    get_a3_config,
    set_a3_config,
)
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class MobilityActor:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST", "GET"])
    def read_a3(request):
        cfg = get_a3_config()
        return success_response({
            "enabled":   cfg.enabled,
            "offset_db": cfg.offset_db,
            "hys_db":    cfg.hys_db,
            "ttt_ms":    cfg.ttt_ms,
        }, "ok")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def set_a3(request):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("invalid JSON", str(e), http_status=400)
        cfg = set_a3_config(
            enabled=body.get("enabled"),
            offset_db=body.get("offset_db"),
            hys_db=body.get("hys_db"),
            ttt_ms=body.get("ttt_ms"),
        )
        logger.info(
            "A3 config updated: enabled=%s offset=%.1fdB hys=%.1fdB ttt=%dms",
            cfg.enabled, cfg.offset_db, cfg.hys_db, cfg.ttt_ms,
        )
        return success_response({
            "enabled":   cfg.enabled,
            "offset_db": cfg.offset_db,
            "hys_db":    cfg.hys_db,
            "ttt_ms":    cfg.ttt_ms,
        }, "A3 config updated")
