"""E2 event log read actor — Dashboard /logs page 拉 E2 plane 事件 timeline。

URL: POST /api/v0.1/E2Adapter/EventLog/EventLogReader/read
Body: { since_seq: int (optional, default 0), limit: int (optional, default 200) }
"""
from __future__ import annotations

import json

from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.e2_adapter.serializers.event_log_serializers import EventLogReadSerializer
from main.apps.e2_adapter.services.optional.event_log.ring import get_ring
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class EventLogActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), status=400)
        since_seq = int(body.get("since_seq", 0))
        limit = int(body.get("limit", 200))
        entries = get_ring().read(since_seq=since_seq, limit=limit)
        payload = {
            "entries": entries,
            "count": len(entries),
            "last_seq": entries[-1]["seq"] if entries else since_seq,
        }
        return success_response(EventLogReadSerializer(payload).data)
