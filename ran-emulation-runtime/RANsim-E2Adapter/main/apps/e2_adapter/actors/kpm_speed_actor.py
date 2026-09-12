"""KPM sim-speed endpoint — Dashboard 切 DU tick 速度時同步通知 adapter,
讓 SCTP indication producer 的 poll 頻率縮放到 sim-time 上的 report_period。
"""
from __future__ import annotations

import json

from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.e2_adapter.services.optional.sctp_link import sim_speed
from main.utils.response import error_response, success_response


class KpmSpeedActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def set(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), status=400)
        speed_x = body.get("sim_speed_x")
        if speed_x is None:
            return error_response("sim_speed_x required", status=400)
        try:
            applied = sim_speed.set_speed(float(speed_x))
        except (TypeError, ValueError):
            return error_response("sim_speed_x must be a number", status=400)
        return success_response({"sim_speed_x": applied}, "adapter sim speed updated")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST", "GET"])
    def read(request: HttpRequest):
        return success_response({"sim_speed_x": sim_speed.get_speed()}, "adapter sim speed")
