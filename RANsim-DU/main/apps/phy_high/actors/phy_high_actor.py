"""phy_high 對外 endpoint — throughput / BLER 查詢工具。"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.mac.services.optional.link_adaptation.mcs_table import (
    mcs_to_throughput_mbps,
    sinr_to_mcs,
)
from main.apps.phy_high.serializers.phy_request_serializers import (
    BlerRequestSerializer,
    ThroughputRequestSerializer,
)
from main.apps.phy_high.services.optional.coding.ldpc_abstract import estimate_bler
from main.apps.phy_high.services.optional.modulation.modulation_table import mcs_to_modulation
from main.utils.response import error_response, success_response


class PhyHighController:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def compute_modulation_throughput(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        ser = ThroughputRequestSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)
        v = ser.validated_data
        # 用 mcs 推 bps_re — 透過 sinr 反向探:這裡簡化採 MCS 對應的 spectral efficiency
        mod_name, order = mcs_to_modulation(v["mcs"])
        # 假 SINR 從 MCS 倒推一個典型值
        proxy_sinr = -7 + v["mcs"] * 1.3
        _, bps_re = sinr_to_mcs(proxy_sinr)
        tput = mcs_to_throughput_mbps(mcs=v["mcs"], bps_re=bps_re, n_rb=v["n_rb"])
        return success_response(
            {
                "modulation": mod_name,
                "modulation_order": order,
                "throughput_mbps": tput * v.get("layers", 1),
            },
            "OK",
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def estimate_bler(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)
        ser = BlerRequestSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)
        v = ser.validated_data
        bler = estimate_bler(v["sinr_db"], v["mcs"])
        return success_response({"sinr_db": v["sinr_db"], "mcs": v["mcs"], "bler": bler}, "OK")
