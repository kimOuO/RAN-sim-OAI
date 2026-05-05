"""HARQ process 查詢 endpoint — 狀態主要由 mac.services.optional.harq.harq_manager 維護。"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.mac.models.harq_process import HarqProcess
from main.apps.mac.serializers.harq_process_serializers import HarqProcessReadSerializer
from main.apps.mac.services.business.relational_db_operations import RelationalDbBusinessService
from main.utils.response import error_response, success_response


class MacHarqController:
    """Component: /api/v0.1/DU/MAC/MacHarqController/<element>"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        filters: dict = {}
        if payload.get("ue_mac_uuid"):
            filters["f_ue_mac_uuid"] = payload["ue_mac_uuid"]
        if payload.get("direction"):
            filters["direction"] = payload["direction"]

        rows = RelationalDbBusinessService.list_entities(HarqProcess, filters)
        data = [HarqProcessReadSerializer(r.__dict__).data for r in rows]
        return success_response(data, "OK")
