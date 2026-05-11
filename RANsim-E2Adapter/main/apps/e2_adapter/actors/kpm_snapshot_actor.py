"""KPM snapshot read actors — Dashboard 顯示 KPM metric 數值用。

URLs:
  POST /api/v0.1/E2Adapter/KpmSnapshot/SnapshotReader/read    — 最新 UE × metric table
  POST /api/v0.1/E2Adapter/KpmSnapshot/RecentReader/read      — 最近 N 筆 flat list
  POST /api/v0.1/E2Adapter/KpmSnapshot/HistoryReader/read     — 單 UE+metric 時序 (sparkline)
"""
from __future__ import annotations

import json

from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.e2_adapter.serializers.kpm_snapshot_serializers import (
    KpmHistoryReadSerializer,
    KpmRecentReadSerializer,
    KpmSnapshotReadSerializer,
)
from main.apps.e2_adapter.services.optional.event_log.kpm_snapshot import get_ring
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class KpmSnapshotActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request: HttpRequest):
        try:
            payload = get_ring().latest_snapshot()
            return success_response(KpmSnapshotReadSerializer(payload).data)
        except Exception as exc:
            logger.exception("KpmSnapshot/read failed")
            return error_response("internal error", str(exc), status=500)


class KpmRecentActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), status=400)
        limit = int(body.get("limit", 50))
        entries = get_ring().recent(limit)
        return success_response(KpmRecentReadSerializer({
            "entries": entries, "count": len(entries),
        }).data)


class KpmHistoryActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), status=400)
        ue_id = body.get("ue_id", "")
        metric = body.get("metric", "")
        limit = int(body.get("limit", 60))
        if not ue_id or not metric:
            return error_response("ue_id + metric required", status=400)
        points = get_ring().history_for(ue_id, metric, limit)
        return success_response(KpmHistoryReadSerializer({
            "ue_id": ue_id, "metric": metric, "points": points,
        }).data)
