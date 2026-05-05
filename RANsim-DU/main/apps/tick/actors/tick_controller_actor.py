"""TickController — start / stop / run_once / read。"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.tick.serializers.tick_state_serializers import TickStateReadSerializer
from main.apps.tick.services.optional.runner.tick_runner import get_tick_runner
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class TickController:
    """Component name in URL: TickController"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def start(request):
        ok = get_tick_runner().start()
        if not ok:
            return error_response("Tick already running", http_status=409)
        logger.info("Tick driver started")
        return success_response(_status_dict(), "Started")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def stop(request):
        ok = get_tick_runner().stop()
        if not ok:
            return error_response("Tick not running", http_status=409)
        logger.info("Tick driver stopped")
        return success_response(_status_dict(), "Stopped")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def run_once(request):
        result = get_tick_runner().run_once()
        return success_response(result, "Tick executed once")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        return success_response(_status_dict(), "OK")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def register_ue(request):
        """測試/開發用:手動把 UE 推進 tick registry。"""
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        ue_id = payload.get("ue_id")
        if not ue_id:
            return error_response("ue_id required", http_status=400)
        get_tick_runner().register_ue(
            ue_id,
            serving_cell=payload.get("serving_cell", "default-cell-0"),
            sinr_db=float(payload.get("sinr_db", 10.0)),
            rsrp_dbm=float(payload.get("rsrp_dbm", -85.0)),
            qos_5qi=int(payload.get("qos_5qi", 9)),
        )
        return success_response({"ue_id": ue_id}, "Registered")


def _status_dict() -> dict:
    runner = get_tick_runner()
    s = runner.status
    return TickStateReadSerializer({
        "tick_count": s.tick_count,
        "sfn": s.sfn,
        "slot": s.slot,
        "started_at_ms": s.started_at_ms,
        "last_tick_ms": s.last_tick_ms,
        "is_running": s.is_running,
    }).data
