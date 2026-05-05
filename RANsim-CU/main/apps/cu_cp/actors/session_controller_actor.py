"""Dashboard-facing controller — list sessions, query state, force handover."""
from __future__ import annotations

import json

from django.db import transaction
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.serializers.session_serializers import (
    GetStateWriteSerializer,
    HandoverWriteSerializer,
    SessionListReadSerializer,
    UeStateReadSerializer,
)
from main.apps.cu_cp.services.business.du_client_operations import DuClientBusinessService
from main.apps.cu_cp.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.apps.cu_cp.services.common.uuid_service import UUIDService
from main.apps.cu_cp.services.optional.f1ap.f1ap_handler import F1apHandler
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class SessionControllerActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def list(request: HttpRequest):
        ues = UeContext.objects.all()
        out = SessionListReadSerializer([
            {
                "ue_id": ue.ue_id,
                "rrc_state": ue.rrc_state,
                "serving_cell": ue.serving_cell,
                "last_measurement_at": ue.last_measurement_at,
            } for ue in ues
        ], many=True).data
        return success_response(list(out), f"{len(out)} session(s)")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def get_state(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)
        serializer = GetStateWriteSerializer(data=body)
        if not serializer.is_valid():
            return error_response("validation failed", serializer.errors, status=400)
        ue_id = serializer.validated_data["ue_id"]
        ue = SqlDbBusinessService.get_or_none(UeContext, "ue_id", ue_id)
        if ue is None:
            return error_response(f"unknown UE {ue_id}", status=404)
        out = UeStateReadSerializer({
            "ue_id": ue.ue_id,
            "rrc_state": ue.rrc_state,
            "serving_cell": ue.serving_cell,
            "rrc_ue_id": ue.rrc_ue_id,
            "amf_ue_ngap_id": ue.amf_ue_ngap_id,
            "ran_ue_ngap_id": ue.ran_ue_ngap_id,
            "gnb_du_id": ue.gnb_du_id,
            "last_measurement_at": ue.last_measurement_at,
        }).data
        return success_response(out)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def handover(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)
        serializer = HandoverWriteSerializer(data=body)
        if not serializer.is_valid():
            return error_response("validation failed", serializer.errors, status=400)

        ue_id = serializer.validated_data["ue_id"]
        target_cell = serializer.validated_data["target_cell"]
        ue = SqlDbBusinessService.get_or_none(UeContext, "ue_id", ue_id)
        if ue is None:
            return error_response(f"unknown UE {ue_id}", status=404)

        now = TimestampService.now()
        ho_uuid = UUIDService.random_uuid()
        SqlDbBusinessService.create_entity(HandoverEvent, {
            "ho_uuid": ho_uuid,
            "ue_id": ue_id,
            "source_cell": ue.serving_cell or "",
            "target_cell": target_cell,
            "trigger": "MANUAL",
            "status": "PREP",
            "started_at": now,
        })
        DuClientBusinessService.post_ue_context_modification(
            F1apHandler.build_ue_context_modification(ue_id, target_cell),
        )
        SqlDbBusinessService.update_entity(
            UeContext, "ue_id", ue_id,
            {"serving_cell": target_cell, "updated_at": now},
        )
        logger.info("Manual HO requested: UE %s → %s", ue_id, target_cell)
        return success_response({"ho_uuid": ho_uuid, "ue_id": ue_id, "target_cell": target_cell})
