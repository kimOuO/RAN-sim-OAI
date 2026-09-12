"""Trajectory endpoints — Dashboard 設 waypoints 寫進 trajectory_store."""
from __future__ import annotations

import json
import logging
import time

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.ue_lifecycle.services.trajectory_store import get_store

logger = logging.getLogger(__name__)


def _ok(data: dict, message: str = "ok") -> JsonResponse:
    return JsonResponse({"success": True, "message": message, "data": data})


def _err(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"success": False, "message": message, "errors": {}}, status=status)


def _parse(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}


class TrajectoryController:
    """URL: /api/v0.1/UE/Trajectory/<elem>"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def set(request: HttpRequest) -> JsonResponse:
        """body = {ue_id, waypoints:[{x,y,z,t_ms},...], mode?, start_at_ms?}"""
        body = _parse(request)
        ue_id = body.get("ue_id")
        waypoints = body.get("waypoints") or []
        mode = body.get("mode", "loop")
        start_at_ms = body.get("start_at_ms") or int(time.time() * 1000)
        if not ue_id:
            return _err("ue_id required")
        try:
            get_store().set(
                ue_id, waypoints=waypoints, start_at_ms=start_at_ms, mode=mode,
            )
        except ValueError as exc:
            return _err(str(exc))
        return _ok({
            "ue_id": ue_id, "waypoints_count": len(waypoints),
            "mode": mode, "start_at_ms": start_at_ms,
        }, message="trajectory set")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def clear(request: HttpRequest) -> JsonResponse:
        body = _parse(request)
        ue_id = body.get("ue_id")
        if not ue_id:
            return _err("ue_id required")
        get_store().clear(ue_id)
        return _ok({"ue_id": ue_id}, message="trajectory cleared")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST", "GET"])
    def list(request: HttpRequest) -> JsonResponse:
        all_traj = get_store().all()
        return _ok({
            "trajectories": {
                ue_id: {
                    "waypoints_count": len(t["waypoints"]),
                    "mode": t.get("mode", "loop"),
                    "start_at_ms": t["start_at_ms"],
                    "duration_ms": t["waypoints"][-1].get("t_ms", 0) if t["waypoints"] else 0,
                }
                for ue_id, t in all_traj.items()
            },
        })
