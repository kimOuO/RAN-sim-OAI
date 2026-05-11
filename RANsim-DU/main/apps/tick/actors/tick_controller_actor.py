"""TickController — start / stop / run_once / read。"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.tick.serializers.tick_state_serializers import TickStateReadSerializer
from main.apps.tick.services.optional.runner.tick_runner import get_tick_runner
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


def _resolve_serving_cell(ue_id: str, fallback: str = "") -> str:
    """Serving cell 優先順序: payload > UeMacState (來自 F1AP UE Context Setup) > fallback.

    對齊真實 OAI: F1AP 是 serving cell 的 source of truth, Dashboard 的 register_ue
    只是運行控制 endpoint, 不該決定 serving cell.
    """
    if fallback:
        return fallback
    try:
        from main.apps.mac.models.ue_mac_state import UeMacState
        row = UeMacState.objects.filter(ue_id=ue_id).only("serving_cell_id").first()
        if row and row.serving_cell_id:
            return row.serving_cell_id
    except Exception:
        pass
    return ""

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
        serving_cell = _resolve_serving_cell(ue_id, payload.get("serving_cell", ""))
        get_tick_runner().register_ue(
            ue_id,
            serving_cell=serving_cell,
            sinr_db=float(payload.get("sinr_db", 10.0)),
            rsrp_dbm=float(payload.get("rsrp_dbm", -85.0)),
            qos_5qi=int(payload.get("qos_5qi", 9)),
        )
        return success_response({"ue_id": ue_id, "serving_cell": serving_cell}, "Registered")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def replace_ues(request):
        """全量替換 _ue_registry — Dashboard Start Sim 推新 UE list 用。

        body: {"ues": [{"ue_id": "...", "serving_cell": "...", ...}, ...]}
        效果：對於不在 incoming list 的舊 UE，呼 unregister_ue 移除；
              對於 incoming 的 UE，register_ue（同 id 會 overwrite）。
        空 list 拒絕（避免誤呼一鍵清庫）。
        """
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        ues_in = payload.get("ues") or []
        if not ues_in:
            return error_response("ues must not be empty", http_status=400)

        runner = get_tick_runner()
        incoming_ids = {u.get("ue_id") for u in ues_in if u.get("ue_id")}
        existing_ids = set(runner._ue_registry.keys())
        stale = existing_ids - incoming_ids

        for old_id in stale:
            runner.unregister_ue(old_id)

        for u in ues_in:
            ue_id = u.get("ue_id")
            if not ue_id:
                continue
            serving_cell = _resolve_serving_cell(ue_id, u.get("serving_cell", ""))
            runner.register_ue(
                ue_id,
                serving_cell=serving_cell,
                sinr_db=float(u.get("sinr_db", 10.0)),
                rsrp_dbm=float(u.get("rsrp_dbm", -85.0)),
                qos_5qi=int(u.get("qos_5qi", 9)),
            )

        logger.info("replace_ues ok: kept=%d removed=%d", len(incoming_ids), len(stale))
        return success_response(
            {"kept": sorted(incoming_ids), "removed": sorted(stale)},
            f"Replaced UEs: kept={len(incoming_ids)} removed={len(stale)}",
        )


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
