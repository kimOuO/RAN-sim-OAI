"""Cell 配置 Actor — CU 透過 ue_context_setup 流程觸發,亦可由本端 admin 直配。"""
from __future__ import annotations

import json

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.mac.models.cell_state import CellState
from main.apps.mac.serializers.cell_state_serializers import (
    CellStateReadSerializer,
    CellStateWriteSerializer,
)
from main.apps.mac.services.business.relational_db_operations import RelationalDbBusinessService
from main.apps.mac.services.common.timestamp_service import TimestampService
from main.apps.mac.services.common.uuid_service import UUIDService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class MacCellController:
    """Component name in URL: /api/v0.1/DU/MAC/MacCellController/<element>"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def create(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        ser = CellStateWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)

        validated = dict(ser.validated_data)
        cell_uuid = UUIDService.generate_uuid("cell", validated["cell_id"])
        ts = TimestampService.now_ms()

        entity_data = {
            "cell_uuid": cell_uuid,
            "cell_created_at": ts,
            "cell_updated_at": ts,
            **validated,
        }

        try:
            obj = RelationalDbBusinessService.upsert_entity(
                CellState, "cell_uuid", cell_uuid, entity_data,
            )
        except Exception as e:
            logger.exception("Cell create failed")
            return error_response(f"Cell create failed: {e}", http_status=500)

        out = CellStateReadSerializer(obj.__dict__).data
        logger.info("MacCellController.create cell_id=%s pci=%s", obj.cell_id, obj.pci)
        return success_response(out, "Cell created", http_status=201)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        cell_id = payload.get("cell_id")
        if cell_id:
            obj = RelationalDbBusinessService.get_entity(CellState, "cell_id", cell_id)
            if not obj:
                return error_response("Cell not found", http_status=404)
            return success_response(CellStateReadSerializer(obj.__dict__).data, "OK")

        rows = RelationalDbBusinessService.list_entities(CellState)
        data = [CellStateReadSerializer(r.__dict__).data for r in rows]
        return success_response(data, "OK")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def update(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        cell_id = payload.pop("cell_id", None)
        if not cell_id:
            return error_response("cell_id is required", http_status=400)

        payload["cell_updated_at"] = TimestampService.now_ms()
        rows = RelationalDbBusinessService.update_entity(
            CellState, "cell_id", cell_id, payload,
        )
        if rows == 0:
            return error_response("Cell not found", http_status=404)
        obj = RelationalDbBusinessService.get_entity(CellState, "cell_id", cell_id)
        return success_response(CellStateReadSerializer(obj.__dict__).data, "Updated")
