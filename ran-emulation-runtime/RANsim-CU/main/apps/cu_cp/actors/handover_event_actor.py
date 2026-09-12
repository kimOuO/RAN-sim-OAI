"""HandoverEvent list endpoint — Dashboard /logs HandoverMap 用。"""
from __future__ import annotations

import json
from datetime import timedelta

from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.utils.response import error_response, success_response


class HandoverEventActor:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def list(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), status=400)

        window_sec = max(1, min(int(body.get("window_sec", 300)), 86400))
        limit = max(1, min(int(body.get("limit", 200)), 1000))

        cutoff = TimestampService.now() - timedelta(seconds=window_sec)
        rows = list(
            HandoverEvent.objects.filter(started_at__gte=cutoff)
            .order_by("-started_at")[:limit]
        )

        return success_response({
            "events": [
                {
                    "ho_uuid": e.ho_uuid,
                    "ue_id": e.ue_id,
                    "source_cell": e.source_cell or "unknown",
                    "target_cell": e.target_cell or "unknown",
                    "trigger": e.trigger,
                    "status": e.status,
                    "ts_ms": int(e.started_at.timestamp() * 1000),
                }
                for e in rows
            ],
            "count": len(rows),
            "window_sec": window_sec,
        })
