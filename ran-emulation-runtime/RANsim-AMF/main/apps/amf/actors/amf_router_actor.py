"""AmfRouter — NGAP 入口(CU → AMF)。回應格式與平台其他服務一致:{success, message, data}。"""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.amf.services import ngap_procedures as ngap
from main.apps.amf.services.registry import get_registry


def _ok(data, message: str = "ok", status: int = 200) -> JsonResponse:
    return JsonResponse({"success": True, "message": message, "data": data}, status=status)


def _err(message: str, errors=None, status: int = 400) -> JsonResponse:
    return JsonResponse({"success": False, "message": message, "errors": errors or {}}, status=status)


def _handle(request, fn, message: str):
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError as exc:
        return _err("invalid JSON", str(exc))
    try:
        return _ok(fn(body), message)
    except ngap.NgapError as exc:
        return _err(exc.cause, exc.detail, exc.status)


class AmfRouterActor:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def ng_setup(request):
        return _handle(request, ngap.ng_setup, "NG Setup Response")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def initial_ue_message(request):
        return _handle(request, ngap.initial_ue_message, "Initial UE Message accepted")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def path_switch_request(request):
        return _handle(request, ngap.path_switch_request, "Path Switch Request Acknowledge")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def handover_required(request):
        return _handle(request, ngap.handover_required, "Handover Command")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def handover_notify(request):
        return _handle(request, ngap.handover_notify, "Handover Notify accepted")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def ue_context_release(request):
        return _handle(request, ngap.ue_context_release, "UE Context Release Complete")


class StatusActor:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST", "GET"])
    def read(request):
        snap = get_registry().snapshot()
        return _ok({"gnb_count": len(snap["gnbs"]), "ue_count": len(snap["ues"]),
                    "connected": sum(1 for u in snap["ues"] if u["cm_state"] == "CONNECTED"),
                    "counters": snap["counters"],
                    "gnbs": [{k: g[k] for k in ("gnb_id", "gnb_name", "cu_url", "plmn", "tac")} for g in snap["gnbs"]]})

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def ues(request):
        return _ok(get_registry().snapshot()["ues"])
