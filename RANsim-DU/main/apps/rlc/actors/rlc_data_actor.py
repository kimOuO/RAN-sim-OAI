"""RLC 資料注入(模擬 F1-U 進來的 SDU)/ buffer status 查詢。"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.rlc.serializers.rlc_entity_serializers import RlcInjectSduSerializer
from main.apps.rlc.services.optional.entities import factory as entity_factory
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class RlcDataController:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def inject_sdu(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        ser = RlcInjectSduSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)

        v = ser.validated_data
        entity = entity_factory.lookup(v["ue_id"], v["bearer_type"], v["bearer_id"])
        if entity is None:
            return error_response("RLC entity not found", http_status=404)

        sdu_id = entity.recv_sdu(v["sdu_bytes"])
        return success_response({"sdu_id": sdu_id, "bo": entity.buffer_status()}, "Injected")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read_buffer_status(request):
        out = []
        for (ue, btype, bid), ent in entity_factory.all_entities():
            out.append({
                "ue_id": ue, "bearer_type": btype, "bearer_id": bid,
                "mode": ent.mode, "buffer_occupancy": ent.buffer_status(),
            })
        return success_response(out, "OK")
