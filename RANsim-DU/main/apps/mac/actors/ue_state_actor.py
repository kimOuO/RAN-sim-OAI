"""UE MAC state — read-only endpoint;狀態主要由 tick 內部 service 維護。"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.mac.models.ue_mac_state import UeMacState
from main.apps.mac.serializers.ue_mac_state_serializers import UeMacStateReadSerializer
from main.apps.mac.services.business.relational_db_operations import RelationalDbBusinessService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class MacUeStateController:
    """Component: /api/v0.1/DU/MAC/MacUeStateController/<element>"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        ue_id = payload.get("ue_id")
        if ue_id:
            obj = RelationalDbBusinessService.get_entity(UeMacState, "ue_id", ue_id)
            if not obj:
                return error_response("UE not found", http_status=404)
            return success_response(UeMacStateReadSerializer(obj.__dict__).data, "OK")

        rows = RelationalDbBusinessService.list_entities(UeMacState)
        data = [UeMacStateReadSerializer(r.__dict__).data for r in rows]
        return success_response(data, "OK")
