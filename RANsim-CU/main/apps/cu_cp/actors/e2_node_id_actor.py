"""E2NodeId/read actor — e2-adapter 啟動時拿 sim 的 globalE2node-ID + RAN function 清單。

URL: POST /api/v0.1/CU/E2/E2NodeId/read

無輸入欄位（adapter 拿全部）。回 sim 從 env 讀的 PLMN/gNB ID 跟 RAN function inventory。
"""
from __future__ import annotations

from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.serializers.e2_node_id_serializers import E2NodeIdReadSerializer
from main.apps.cu_cp.services.optional.e2.global_e2_node_id import read_global_e2_node_id
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


logger = get_logger(__name__)


class E2NodeIdActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request: HttpRequest):
        try:
            payload = read_global_e2_node_id()
            output = E2NodeIdReadSerializer(payload).data
            return success_response(output)
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception("E2NodeId/read failed")
            return error_response("internal error", str(exc), status=500)
