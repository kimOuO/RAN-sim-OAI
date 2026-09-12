"""響應格式標準化 — 鐵則 3-2-3 utils 必備。

Actor 回傳一律透過這兩個 helper，不得直接 return JsonResponse / Response。

注：用 Django JsonResponse（不用 DRF Response），因為 actor 多為 plain
django view（@csrf_exempt + @require_http_methods），DRF Response 沒有
accepted_renderer 上下文會在 render 時 assert 失敗。
"""
from typing import Any

from django.http import JsonResponse


def success_response(data: Any, message: str = "OK", http_status: int = 200) -> JsonResponse:
    return JsonResponse(
        {
            "success": True,
            "message": message,
            "data": data,
        },
        status=http_status,
    )


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
    return JsonResponse(body, status=http_status)
