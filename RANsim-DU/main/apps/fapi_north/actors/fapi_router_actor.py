"""FapiRouter — RU 上報 CQI / CRC 進來,DU 用來推 link adaptation / HARQ。"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.fapi_north.serializers.fapi_message_serializers import (
    CqiIndicationSerializer,
    CrcIndicationSerializer,
)
from main.apps.mac.services.optional.harq.harq_manager import get_harq_manager
from main.apps.mac.services.optional.link_adaptation.mcs_controller import get_mcs_controller
from main.apps.mac.services.common.timestamp_service import TimestampService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class FapiRouterController:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def cqi_indication(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        ser = CqiIndicationSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)
        v = ser.validated_data
        new_mcs, smoothed_bler = get_mcs_controller().update(
            v["ue_id"], v["sinr_db"], TimestampService.now_ms(),
        )
        logger.debug(
            "CQI ind ue=%s sinr=%.1f cqi=%d → mcs=%d bler=%.3f",
            v["ue_id"], v["sinr_db"], v["cqi"], new_mcs, smoothed_bler,
        )
        return success_response(
            {"ue_id": v["ue_id"], "new_mcs": new_mcs, "smoothed_bler": smoothed_bler},
            "OK",
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def crc_indication(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        ser = CrcIndicationSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)
        v = ser.validated_data
        # 預設 CRC ind 是 UL CRC(對齊 OAI 概念);DL CRC 由 PUCCH 帶 ACK,簡化只走 UL。
        st = get_harq_manager().handle_feedback(
            v["ue_id"], v["harq_pid"], "UL", v["success"],
        )
        return success_response(
            {"ue_id": v["ue_id"], "harq_pid": v["harq_pid"], "state": st.state if st else "UNKNOWN"},
            "OK",
        )
