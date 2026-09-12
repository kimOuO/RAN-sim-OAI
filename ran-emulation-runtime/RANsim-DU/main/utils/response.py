"""統一 HTTP 回應格式。"""
from __future__ import annotations

from typing import Any

from django.http import JsonResponse


def success_response(data: Any = None, message: str = "OK", http_status: int = 200) -> JsonResponse:
    body = {"status": "success", "message": message, "data": data}
    return JsonResponse(body, status=http_status, json_dumps_params={"ensure_ascii": False})


def error_response(message: str, errors: Any = None, http_status: int = 400) -> JsonResponse:
    body = {"status": "error", "message": message, "errors": errors}
    return JsonResponse(body, status=http_status, json_dumps_params={"ensure_ascii": False})
