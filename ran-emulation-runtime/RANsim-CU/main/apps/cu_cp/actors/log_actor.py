"""Logs/Ring/read endpoint — Dashboard /logs page 拉訊息日誌。"""
from __future__ import annotations

import json

from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.services.optional.logs.ran_message_log import get_ring
from main.utils.response import error_response, success_response


class LogActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read_ring(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), status=400)
        since_seq = int(body.get("since_seq", 0))
        limit = int(body.get("limit", 500))
        entries = get_ring().read(since_seq=since_seq, limit=limit)
        return success_response({
            "entries": entries,
            "count": len(entries),
            "last_seq": entries[-1]["seq"] if entries else since_seq,
        })
