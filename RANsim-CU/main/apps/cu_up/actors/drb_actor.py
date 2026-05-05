"""DRB observability actor — list / read for dashboards."""
from __future__ import annotations

import json

from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_up.models.drb import Drb
from main.apps.cu_up.serializers.e1ap_serializers import DrbReadSerializer
from main.apps.cu_up.services.business.sqldb_operations import SqlDbBusinessService
from main.utils.response import error_response, success_response


class DrbActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def list(request: HttpRequest):
        out = []
        for drb in Drb.objects.all():
            out.append(DrbReadSerializer({
                "ue_id": drb.ue_id,
                "drb_id": drb.drb_id,
                "qos_5qi": drb.qos_5qi,
                "rlc_mode": drb.rlc_mode,
                "gtp_teid_ul": drb.gtp_teid_ul,
                "gtp_teid_dl": drb.gtp_teid_dl,
                "dl_packets": drb.dl_packets,
                "ul_packets": drb.ul_packets,
            }).data)
        return success_response(out, f"{len(out)} drb(s)")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)
        ue_id = body.get("ue_id")
        drb_id = body.get("drb_id")
        if not ue_id or drb_id is None:
            return error_response("ue_id and drb_id required", status=400)
        drb = SqlDbBusinessService.get_or_none(Drb, "drb_uuid",
            f"drb-{abs(hash(f'{ue_id}:{drb_id}'))}")
        if drb is None:
            drb = Drb.objects.filter(ue_id=ue_id, drb_id=drb_id).first()
        if drb is None:
            return error_response("drb not found", status=404)
        return success_response(DrbReadSerializer({
            "ue_id": drb.ue_id, "drb_id": drb.drb_id,
            "qos_5qi": drb.qos_5qi, "rlc_mode": drb.rlc_mode,
            "gtp_teid_ul": drb.gtp_teid_ul, "gtp_teid_dl": drb.gtp_teid_dl,
            "dl_packets": drb.dl_packets, "ul_packets": drb.ul_packets,
        }).data)
