"""ComputeActor — per-tick 計算 entry point。

請求鏈（鐵則 2-1）：
  Client → main/urls.py → api/urls.py → ComputeActor.compute
    → Serializer (驗證)
    → Business Service (sionna_operations)
    → Optional Service (ran_calculation)
    → 回傳
"""
import time

from rest_framework.decorators import api_view

from main.apps.ran_signal.serializers.compute_serializers import (
    ComputeRequestSerializer,
    ComputeResponseSerializer,
)
from main.apps.ran_signal.services.business.sionna_operations import SionnaBusinessService
from main.apps.ran_signal.services.common.timestamp_service import TimestampService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


logger = get_logger(__name__)


class ComputeActor:
    """Actor for per-tick RAN simulation compute."""

    @staticmethod
    @api_view(["POST"])  # 鐵則 7-2 全 POST
    def compute(request):
        started_ms = TimestampService.now_ms()

        # Step 1: 驗證請求
        req_ser = ComputeRequestSerializer(data=request.data)
        if not req_ser.is_valid():
            return error_response(
                "Validation failed",
                errors=req_ser.errors,
                http_status=400,
            )
        validated = req_ser.validated_data

        # Step 2: 檢查 scene_id 對得上載入的 scene
        if not SionnaBusinessService.is_scene_loaded(validated["scene_id"]):
            return error_response(
                f"scene_id '{validated['scene_id']}' not loaded on this server",
                http_status=404,
            )

        # Step 3: 呼叫 Business Service 跑模擬
        try:
            compute_result = SionnaBusinessService.compute_tick(
                timestamp_ms=validated["timestamp_ms"],
                scene_id=validated["scene_id"],
                ue_positions=validated["ue_positions"],
            )
        except MemoryError as exc:
            logger.error("GPU OOM on compute: %s", exc)
            return error_response("GPU out of memory", http_status=503)
        except RuntimeError as exc:
            logger.exception("Runtime error on compute")
            return error_response(str(exc), http_status=503)

        elapsed_ms = TimestampService.now_ms() - started_ms

        # Step 4: 格式化回傳
        payload = {
            "timestamp_ms": validated["timestamp_ms"],
            "compute_ms": elapsed_ms,
            "tick_ms": compute_result.get("tick_ms", 500),
            "e2": compute_result["e2"],
            "ue_status": compute_result["ue_status"],
            "pm": compute_result.get("pm", {}),
            "bbu_status": compute_result.get("bbu_status", {}),
            "warnings": compute_result.get("warnings", []),
        }

        resp_ser = ComputeResponseSerializer(payload)
        logger.info(
            "compute tick: ts=%d ues=%d cells=%d elapsed=%dms",
            validated["timestamp_ms"],
            len(validated["ue_positions"]),
            len(payload["e2"]),
            elapsed_ms,
        )
        return success_response(resp_ser.data, message="OK", http_status=200)
