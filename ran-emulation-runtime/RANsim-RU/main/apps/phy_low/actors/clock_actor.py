"""LockstepClock — 全場鎖步時鐘的控制(多 gNB D1)。

  POST /api/v0.1/RU/State/LockstepClock/start        {sim_dt_ms, speed_x}
  POST /api/v0.1/RU/State/LockstepClock/stop
  POST /api/v0.1/RU/State/LockstepClock/set_speed    {speed_x, sim_dt_ms?}
  POST /api/v0.1/RU/State/LockstepClock/align_scene  劇本時鐘從此刻歸零
  POST /api/v0.1/RU/State/LockstepClock/read         {running, tick, scene_sim_ms, achieved_speed_x, …}
"""
import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.phy_low.services.optional.lockstep_clock import get_clock
from main.utils.response import error_response, success_response


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


class LockstepClockController:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def start(request):
        try:
            p = _body(request)
            ok = get_clock().start(sim_dt_ms=int(p.get("sim_dt_ms") or 500), speed_x=float(p.get("speed_x") or 1.0))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return error_response("Invalid body", str(exc), 400)
        return success_response(get_clock().status(), "Started" if ok else "Already running (no-op)", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def stop(request):
        ok = get_clock().stop()
        return success_response(get_clock().status(), "Stopped" if ok else "Already stopped (no-op)", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def set_speed(request):
        try:
            p = _body(request)
            get_clock().set_speed(float(p["speed_x"]), p.get("sim_dt_ms"))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return error_response("Invalid body", str(exc), 400)
        return success_response(get_clock().status(), "Speed set", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def align_scene(request):
        origin = get_clock().align_scene()
        return success_response({"origin_tick": origin, **get_clock().status()}, "Aligned", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        return success_response(get_clock().status(), "OK", 200)
