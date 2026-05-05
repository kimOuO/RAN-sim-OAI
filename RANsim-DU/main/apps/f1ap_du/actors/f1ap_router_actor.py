"""F1ApRouter — DU 收 CU 訊息的入口。"""
from __future__ import annotations

import json

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from ran_sim_protocol.f1ap import UeContextSetupResponse

from main.apps.f1ap_du.serializers.f1ap_message_serializers import (
    DlRrcMessageTransferSerializer,
    F1SetupResponseSerializer,
    UeContextReleaseSerializer,
    UeContextSetupSerializer,
)
from main.apps.f1ap_du.services.optional.message_codec.f1ap_codec import (
    encode_ue_context_setup_response,
)
from main.apps.mac.models.ue_mac_state import UeMacState
from main.apps.mac.services.business.relational_db_operations import (
    RelationalDbBusinessService as MacRelDb,
)
from main.apps.mac.services.common.timestamp_service import TimestampService as MacTs
from main.apps.mac.services.common.uuid_service import UUIDService as MacUuid
from main.apps.mac.services.optional.harq.harq_manager import get_harq_manager
from main.apps.mac.services.optional.random_access.ra_manager import get_ra_manager
from main.apps.rlc.models.rlc_entity import RlcEntity
from main.apps.rlc.services.business.relational_db_operations import (
    RelationalDbBusinessService as RlcRelDb,
)
from main.apps.rlc.services.common.timestamp_service import TimestampService as RlcTs
from main.apps.rlc.services.common.uuid_service import UUIDService as RlcUuid
from main.apps.rlc.services.optional.entities import factory as rlc_factory
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class F1ApRouterController:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def ue_context_setup(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        ser = UeContextSetupSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)
        v = ser.validated_data
        ue_id = v["ue_id"]

        # MAC: create or update UE state
        ue_mac_uuid = MacUuid.generate_uuid("ue_mac", ue_id)
        ts_mac = MacTs.now_ms()
        MacRelDb.upsert_entity(
            UeMacState, "ue_mac_uuid", ue_mac_uuid,
            {
                "ue_mac_uuid": ue_mac_uuid,
                "ue_id": ue_id,
                "serving_cell_id": payload.get("serving_cell_id", ""),
                "ue_mac_created_at": ts_mac,
                "ue_mac_updated_at": ts_mac,
            },
        )

        # RA + HARQ in-memory hooks
        get_ra_manager().msg1_detected(ue_id, ts_mac)
        get_harq_manager().add_ue(ue_id)

        # RLC: 為每個 DRB 建 entity
        ts_rlc = RlcTs.now_ms()
        drbs_setup: list[int] = []
        for drb in v.get("drbs", []):
            drb_id = drb["drb_id"]
            mode = drb.get("rlc_mode", "AM")
            key = f"{ue_id}:DRB:{drb_id}"
            rlc_uuid = RlcUuid.generate_uuid("rlc", key)
            RlcRelDb.upsert_entity(
                RlcEntity, "rlc_uuid", rlc_uuid,
                {
                    "rlc_uuid": rlc_uuid,
                    "ue_id": ue_id,
                    "bearer_type": "DRB",
                    "bearer_id": drb_id,
                    "mode": mode,
                    "sn_field_length": 12,
                    "rlc_created_at": ts_rlc,
                    "rlc_updated_at": ts_rlc,
                },
            )
            ent = rlc_factory.make_entity(mode)
            rlc_factory.register(ue_id, "DRB", drb_id, ent)
            drbs_setup.append(drb_id)

        # SRB1 預設配 AM
        srb_key = f"{ue_id}:SRB:1"
        srb_uuid = RlcUuid.generate_uuid("rlc", srb_key)
        RlcRelDb.upsert_entity(
            RlcEntity, "rlc_uuid", srb_uuid,
            {
                "rlc_uuid": srb_uuid,
                "ue_id": ue_id,
                "bearer_type": "SRB",
                "bearer_id": 1,
                "mode": "AM",
                "sn_field_length": 12,
                "rlc_created_at": ts_rlc,
                "rlc_updated_at": ts_rlc,
            },
        )
        rlc_factory.register(ue_id, "SRB", 1, rlc_factory.make_entity("AM"))

        get_ra_manager().finalize(ue_id)
        logger.info("UE context setup ok ue=%s drbs=%s", ue_id, drbs_setup)

        resp = UeContextSetupResponse(ue_id=ue_id, success=True, drb_setup_list=drbs_setup)
        return success_response(encode_ue_context_setup_response(resp), "OK", http_status=201)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def ue_context_release(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        ser = UeContextReleaseSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)
        ue_id = ser.validated_data["ue_id"]

        UeMacState.objects.filter(ue_id=ue_id).delete()
        RlcEntity.objects.filter(ue_id=ue_id).delete()
        rlc_factory.unregister_ue(ue_id)
        get_harq_manager().remove_ue(ue_id)
        logger.info("UE context release ue=%s", ue_id)
        return success_response({"ue_id": ue_id}, "Released")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def dl_rrc_message(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        ser = DlRrcMessageTransferSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)
        v = ser.validated_data

        # 把 RRC PDU 推到對應 SRB1 的 RLC TX queue (假 size = b64 length)
        ue_id = v["ue_id"]
        ent = rlc_factory.lookup(ue_id, "SRB", 1)
        if ent is None:
            logger.warning("DL RRC for ue=%s but no SRB1 entity", ue_id)
            return error_response("UE SRB1 not found", http_status=404)
        msg_size = max(1, len(v["rrc_msg_b64"]) * 3 // 4)  # b64 → 原 bytes 估算
        ent.recv_sdu(msg_size)
        logger.info("DL RRC injected to SRB1 ue=%s size=%dB", ue_id, msg_size)
        return success_response({"ue_id": ue_id, "queued_bytes": msg_size}, "OK")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def f1_setup_response_callback(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        ser = F1SetupResponseSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)
        # 簡化:只記 log
        logger.info(
            "F1Setup response from CU tid=%s accepted=%s",
            ser.validated_data.get("transaction_id"),
            ser.validated_data.get("accepted"),
        )
        return success_response(None, "OK")
