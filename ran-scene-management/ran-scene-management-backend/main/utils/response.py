"""Standardised HTTP response builders. Actors must use these instead of
returning JsonResponse directly."""
from __future__ import annotations

from typing import Any

from django.http import JsonResponse


def success_response(
    data: Any = None,
    message: str = "ok",
    status: int = 200,
) -> JsonResponse:
    payload = {
        "success": True,
        "message": message,
        "data": data if data is not None else {},
    }
    return JsonResponse(payload, status=status, safe=False)


def error_response(
    message: str,
    errors: Any = None,
    status: int = 400,
) -> JsonResponse:
    payload = {
        "success": False,
        "message": message,
        "errors": errors if errors is not None else {},
    }
    return JsonResponse(payload, status=status, safe=False)
