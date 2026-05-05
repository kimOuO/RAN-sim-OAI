"""響應格式標準化 — 鐵則 3-2-3 utils 必備。

Actor 回傳一律透過這兩個 helper，不得直接 return JsonResponse / Response。
"""
from typing import Any

from rest_framework import status as drf_status
from rest_framework.response import Response


def success_response(data: Any, message: str = "OK", http_status: int = drf_status.HTTP_200_OK) -> Response:
    return Response(
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
    http_status: int = drf_status.HTTP_400_BAD_REQUEST,
) -> Response:
    body: dict[str, Any] = {
        "success": False,
        "message": message,
    }
    if errors is not None:
        body["errors"] = errors
    return Response(body, status=http_status)
