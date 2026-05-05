"""RLC entity CRUD — 通常由 f1ap_du.UeContextSetup 觸發,但也對外開 endpoint 方便測試。"""
from __future__ import annotations

import json

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.rlc.models.rlc_entity import RlcEntity
from main.apps.rlc.serializers.rlc_entity_serializers import (
    RlcEntityReadSerializer,
    RlcEntityWriteSerializer,
)
from main.apps.rlc.services.business.relational_db_operations import RelationalDbBusinessService
from main.apps.rlc.services.common.timestamp_service import TimestampService
from main.apps.rlc.services.common.uuid_service import UUIDService
from main.apps.rlc.services.optional.entities import factory as entity_factory
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class RlcEntityController:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def create(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        ser = RlcEntityWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)

        validated = dict(ser.validated_data)
        key = f"{validated['ue_id']}:{validated['bearer_type']}:{validated['bearer_id']}"
        rlc_uuid = UUIDService.generate_uuid("rlc", key)
        ts = TimestampService.now_ms()

        entity_data = {
            "rlc_uuid": rlc_uuid,
            "rlc_created_at": ts,
            "rlc_updated_at": ts,
            **validated,
        }

        try:
            obj = RelationalDbBusinessService.upsert_entity(
                RlcEntity, "rlc_uuid", rlc_uuid, entity_data,
            )
            entity = entity_factory.make_entity(
                validated["mode"], sn_field_length=validated.get("sn_field_length", 12),
            )
            entity_factory.register(
                validated["ue_id"], validated["bearer_type"], validated["bearer_id"], entity,
            )
        except Exception as e:
            logger.exception("RLC entity create failed")
            return error_response(f"RLC entity create failed: {e}", http_status=500)

        return success_response(
            RlcEntityReadSerializer(obj.__dict__).data, "RLC entity created", http_status=201,
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        filters = {k: payload[k] for k in ("ue_id", "bearer_type", "bearer_id") if k in payload}
        rows = RelationalDbBusinessService.list_entities(RlcEntity, filters)
        data = [RlcEntityReadSerializer(r.__dict__).data for r in rows]
        return success_response(data, "OK")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def delete(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        ue_id = payload.get("ue_id")
        if not ue_id:
            return error_response("ue_id required", http_status=400)
        bearer_type = payload.get("bearer_type")
        bearer_id = payload.get("bearer_id")
        if bearer_type and bearer_id is not None:
            RelationalDbBusinessService.delete_entity(
                RlcEntity, "ue_id", ue_id,
            )
            entity_factory.unregister(ue_id, bearer_type, bearer_id)
        else:
            RlcEntity.objects.filter(ue_id=ue_id).delete()
            entity_factory.unregister_ue(ue_id)
        return success_response(None, "Deleted")
