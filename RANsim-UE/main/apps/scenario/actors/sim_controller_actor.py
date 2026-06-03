"""SimController — Stage 2 unified sim start/stop entry.

POST /api/v0.1/UE/Sim/SimController/start
  body: {source: "live_db" | "scenario", scenario_id?: str, speed_x?: number}

兩條路徑(/editor 拉拖跟 /scenarios 劇本)未來都打這支。
"""
from __future__ import annotations

import json
import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.scenario.services import sim_orchestrator


logger = logging.getLogger(__name__)


def _ok(data: dict, message: str = "ok") -> JsonResponse:
    return JsonResponse({"success": True, "message": message, "data": data})


def _err(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse(
        {"success": False, "message": message, "errors": {}}, status=status,
    )


def _parse(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}


class SimController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def start(request: HttpRequest) -> JsonResponse:
        payload = _parse(request)
        source = (payload.get("source") or "").strip().lower()
        if source not in ("live_db", "scenario"):
            return _err("source must be 'live_db' or 'scenario'", status=400)
        scenario_id = payload.get("scenario_id") or ""
        speed_x = float(payload.get("speed_x") or 1.0)
        sim_dt_ms = int(payload.get("sim_dt_ms") or 500)
        try:
            result = sim_orchestrator.start_sim(
                source, scenario_id=scenario_id, speed_x=speed_x, sim_dt_ms=sim_dt_ms,
            )
        except ValueError as e:
            return _err(str(e), status=400)
        except RuntimeError as e:
            return _err(str(e), status=409)
        except Exception as e:  # noqa: BLE001
            logger.exception("SimController.start failed")
            return _err(f"sim start failed: {e}", status=500)
        return _ok(result, "sim started")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def stop(request: HttpRequest) -> JsonResponse:
        result = sim_orchestrator.stop_sim()
        return _ok(result, "sim stopped")
