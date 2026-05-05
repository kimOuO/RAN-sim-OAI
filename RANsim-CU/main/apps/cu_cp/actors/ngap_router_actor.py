"""NGAP router — handles 5GC → CU messages.

OAI ref: openair3/NGAP/ngap_gNB_handlers.c.
"""
from __future__ import annotations

import json

from django.db import transaction
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.serializers.ngap_serializers import (
    DownlinkNasTransportWriteSerializer,
    InitialContextSetupWriteSerializer,
    InitialUeMessageWriteSerializer,
)
from main.apps.cu_cp.services.business.cuup_client_operations import CuupClientBusinessService
from main.apps.cu_cp.services.business.du_client_operations import DuClientBusinessService
from main.apps.cu_cp.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.apps.cu_cp.services.optional.f1ap.f1ap_handler import F1apHandler
from main.apps.cu_cp.services.optional.rrc.message_handler import RrcMessageHandler
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


def _parse_or_400(request: HttpRequest, serializer_cls):
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError as exc:
        return None, error_response("invalid JSON", str(exc), status=400)
    serializer = serializer_cls(data=body)
    if not serializer.is_valid():
        return None, error_response("validation failed", serializer.errors, status=400)
    return serializer.validated_data, None


class NgapRouterActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def initial_ue_message(request: HttpRequest):
        """5GC -> CU echo path for testing; normally CU originates this."""
        data, err = _parse_or_400(request, InitialUeMessageWriteSerializer)
        if err is not None:
            return err
        logger.info("InitialUEMessage echoed: ran_ue_ngap_id=%s", data["ran_ue_ngap_id"])
        return success_response(data, "received")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def initial_context_setup(request: HttpRequest):
        """5GC → CU. Triggers E1 Bearer Setup + F1 UE Context Setup."""
        data, err = _parse_or_400(request, InitialContextSetupWriteSerializer)
        if err is not None:
            return err

        ran_ue_ngap_id = data["ran_ue_ngap_id"]
        amf_ue_ngap_id = data["amf_ue_ngap_id"]
        sessions = data["pdu_session_resources"]

        ue = SqlDbBusinessService.get_or_none(UeContext, "ran_ue_ngap_id", ran_ue_ngap_id)
        if ue is None:
            return error_response(f"unknown RAN-UE-NGAP-ID {ran_ue_ngap_id}", status=404)

        SqlDbBusinessService.update_entity(
            UeContext, "ue_id", ue.ue_id,
            {"amf_ue_ngap_id": amf_ue_ngap_id, "updated_at": TimestampService.now()},
        )

        # Build DRB list (one DRB per PDU session, mirroring OAI restriction).
        drbs = []
        for idx, sess in enumerate(sessions):
            drbs.append({
                "drb_id": idx + 1,
                "qos_5qi": (sess.get("qos_flow_5qi") or [9])[0],
                "rlc_mode": "AM",
            })

        # E1 Bearer Setup → CU-UP
        bearer_resp = CuupClientBusinessService.bearer_context_setup({
            "ue_id": ue.ue_id,
            "drbs": drbs,
        })

        # F1 UE Context Setup → DU (carrying the RRCReconfiguration)
        rrc_b64 = RrcMessageHandler.encode_rrc_reconfiguration(transaction_id=1, drbs=drbs)
        DuClientBusinessService.post_ue_context_setup(
            F1apHandler.build_ue_context_setup(ue.ue_id, drbs, rrc_b64),
        )

        logger.info("InitialContextSetup processed for %s (%d DRBs)", ue.ue_id, len(drbs))
        return success_response({
            "ue_id": ue.ue_id,
            "drbs": drbs,
            "cu_up_bearer_setup": bearer_resp,
        }, "context setup")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def downlink_nas_transport(request: HttpRequest):
        """5GC → CU → UE. Wraps NAS PDU in DL RRC and forwards to DU."""
        data, err = _parse_or_400(request, DownlinkNasTransportWriteSerializer)
        if err is not None:
            return err

        ran_ue_ngap_id = data["ran_ue_ngap_id"]
        ue = SqlDbBusinessService.get_or_none(UeContext, "ran_ue_ngap_id", ran_ue_ngap_id)
        if ue is None:
            return error_response(f"unknown RAN-UE-NGAP-ID {ran_ue_ngap_id}", status=404)

        rrc_b64 = RrcMessageHandler.encode("DLInformationTransfer", {
            "nas_pdu_b64": data["nas_pdu_b64"],
        })
        downstream = DuClientBusinessService.post_dl_rrc_message(
            F1apHandler.build_dl_rrc_message_transfer(ue.ue_id, rrc_b64),
        )
        return success_response({"ue_id": ue.ue_id, "downstream": downstream}, "NAS forwarded")
