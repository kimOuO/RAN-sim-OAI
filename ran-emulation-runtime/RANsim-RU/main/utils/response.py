"""響應格式 — backend_rule §3-2-3 utils 必備。

Actors 用 plain Django views (`@require_http_methods`) 而非 DRF `APIView`，
所以這裡回 Django 的 `JsonResponse`，不是 DRF 的 `Response`（後者需要
`accepted_renderer` 上下文，否則 .render() 會 crash）。

Actor 一律透過 success_response / error_response 回傳，禁止直接 return JsonResponse。
"""
from typing import Any

from django.http import JsonResponse


def success_response(
    data: Any = None,
    message: str = "OK",
    http_status: int = 200,
) -> JsonResponse:
    payload = {
        "success": True,
        "message": message,
        "data": data if data is not None else {},
    }
    return JsonResponse(payload, status=http_status, json_dumps_params={"ensure_ascii": False})


def error_response(
    message: str,
    errors: Any = None,
    http_status: int = 400,
) -> JsonResponse:
    body: dict[str, Any] = {
        "success": False,
        "message": message,
    }
    if errors is not None:
        body["errors"] = errors
    return JsonResponse(body, status=http_status, json_dumps_params={"ensure_ascii": False})
