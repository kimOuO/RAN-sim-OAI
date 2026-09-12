"""ScenarioController — start/stop/status endpoints for Phase B scenario driver."""
from __future__ import annotations

import json
import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.scenario.services import scenario_driver


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


class ScenarioController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def start(request: HttpRequest) -> JsonResponse:
        """Body: {scenario_id, target_wall_tick_ms?}"""
        payload = _parse(request)
        scenario_id = payload.get("scenario_id")
        if not scenario_id:
            return _err("scenario_id required", status=400)
        target_wall_tick_ms = int(payload.get("target_wall_tick_ms", 500))
        try:
            drv = scenario_driver.start_scenario(
                scenario_id, target_wall_tick_ms=target_wall_tick_ms,
            )
        except (RuntimeError, ValueError) as e:
            return _err(str(e), status=409)
        except Exception as e:
            logger.exception("Failed to start scenario")
            return _err(f"Failed to start scenario: {e}", status=500)
        return _ok(drv.state, "Scenario started")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def stop(request: HttpRequest) -> JsonResponse:
        ok = scenario_driver.stop_scenario()
        drv = scenario_driver.get_driver()
        state = drv.state if drv else {"running": False}
        return _ok(
            state,
            "Scenario stopped" if ok else "No scenario was running (no-op)",
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def status(request: HttpRequest) -> JsonResponse:
        drv = scenario_driver.get_driver()
        if drv is None:
            return _ok({"running": False}, "No driver loaded")
        return _ok(drv.live_state(), "OK")
