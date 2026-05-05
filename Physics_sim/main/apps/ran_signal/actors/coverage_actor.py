"""CoverageActor — 產 per-gNB 2D RSRP 網格（coverage map）。

對齊外部平台 spec：前端 / 另一個 backend 會 call 這個 endpoint 拿 JSON 做熱圖。
"""
from datetime import datetime, timezone

from rest_framework.decorators import api_view

from main.apps.ran_signal.serializers.coverage_serializers import (
    CoverageMapRequestSerializer,
    CoverageMapResponseSerializer,
)
from main.apps.ran_signal.services.business.sionna_operations import SionnaBusinessService
from main.apps.ran_signal.services.common.timestamp_service import TimestampService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


logger = get_logger(__name__)


class CoverageActor:
    @staticmethod
    @api_view(["POST"])
    def compute(request):
        """產 coverage map（per-gNB RSRP 網格）。"""
        req_ser = CoverageMapRequestSerializer(data=request.data)
        if not req_ser.is_valid():
            return error_response("Validation failed", errors=req_ser.errors, http_status=400)

        validated = req_ser.validated_data

        # scene_id 對不上則 404
        if not SionnaBusinessService.is_scene_loaded(validated["scene_id"]):
            return error_response(
                f"scene_id '{validated['scene_id']}' not loaded on this server",
                http_status=404,
            )

        started_ms = TimestampService.now_ms()
        try:
            result = SionnaBusinessService.compute_coverage(
                grid=validated["grid"],
                include_sinr=validated["include_sinr"],
                max_depth=validated["max_depth"],
                null_threshold_dbm=validated["null_threshold_dbm"],
            )
        except MemoryError:
            logger.error("GPU OOM on coverage_map")
            return error_response("GPU out of memory for coverage grid", http_status=503)
        except RuntimeError as exc:
            logger.exception("Coverage compute RuntimeError")
            return error_response(str(exc), http_status=500)

        elapsed_ms = TimestampService.now_ms() - started_ms

        payload = {
            "scene_id": validated["scene_id"],
            "ts": datetime.now(timezone.utc).isoformat(),
            "compute_ms": elapsed_ms,
            "grid": result["grid"],
            "gnbs": result["gnbs"],
        }

        resp_ser = CoverageMapResponseSerializer(payload)
        logger.info(
            "coverage: scene_id=%s gnbs=%d grid=%dx%d elapsed=%dms",
            validated["scene_id"], len(payload["gnbs"]),
            payload["grid"]["n_rows"], payload["grid"]["n_cols"], elapsed_ms,
        )
        return success_response(resp_ser.data, message="OK", http_status=200)
