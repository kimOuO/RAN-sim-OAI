"""Lifecycle endpoints — Status read + push sync from CU/Dashboard。"""
from __future__ import annotations

import json
import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.ue_lifecycle.services.manager import get_manager

logger = logging.getLogger(__name__)


def _ok(data: dict, message: str = "ok", status: int = 200) -> JsonResponse:
    return JsonResponse({"success": True, "message": message, "data": data}, status=status)


def _err(message: str, errors: dict | str | None = None, status: int = 400) -> JsonResponse:
    return JsonResponse(
        {"success": False, "message": message, "errors": errors or {}}, status=status,
    )


def _parse_body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}


class LifecycleController:
    """URL component: Lifecycle"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def sync(request: HttpRequest) -> JsonResponse:
        """CU / Dashboard 通知: attach / detach / profile_changed / sim_start / sim_stop."""
        body = _parse_body(request)
        event = body.get("event", "")
        ue_id = body.get("ue_id")
        if not event:
            return _err("event required", status=400)
        result = get_manager().push_sync(event=event, ue_id=ue_id)
        if not result.get("ok"):
            return _err(result.get("error", "sync failed"))
        return _ok(result)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def start(request: HttpRequest) -> JsonResponse:
        """Sim Start - 所有 thread STANDBY → RUNNING"""
        result = get_manager().push_sync(event="sim_start")
        return _ok(result, message="sim started")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def stop(request: HttpRequest) -> JsonResponse:
        """Sim Stop - 所有 thread RUNNING → STANDBY"""
        result = get_manager().push_sync(event="sim_stop")
        return _ok(result, message="sim stopped")


class StatusController:
    """URL component: Status"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST", "GET"])
    def read(request: HttpRequest) -> JsonResponse:
        """列當前管的 UE + 狀態。"""
        return _ok(get_manager().snapshot())
