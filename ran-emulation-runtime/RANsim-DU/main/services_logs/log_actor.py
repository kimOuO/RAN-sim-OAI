"""Logs/Ring/read endpoint — Dashboard /logs page 拉訊息日誌。"""
from __future__ import annotations
import json
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.services_logs.ran_message_log import get_ring


def _success(data: dict, msg: str = "ok") -> JsonResponse:
    return JsonResponse({"success": True, "message": msg, "data": data}, status=200)


def _error(msg: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"success": False, "message": msg, "data": {}}, status=status)


class LogActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read_ring(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return _error(f"Invalid JSON: {e}")
        since_seq = int(body.get("since_seq", 0))
        limit = int(body.get("limit", 500))
        entries = get_ring().read(since_seq=since_seq, limit=limit)
        return _success({
            "entries": entries,
            "count": len(entries),
            "last_seq": entries[-1]["seq"] if entries else since_seq,
        })
