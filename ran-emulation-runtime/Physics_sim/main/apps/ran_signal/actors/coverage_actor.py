"""CoverageActor — 產 per-gNB 2D RSRP 網格（coverage map）。

對齊外部平台 spec：前端 / 另一個 backend 會 call 這個 endpoint 拿 JSON 做熱圖。

優先權設計：Coverage 有最高優先權。
- 開始 compute 前先呼 DU 停 tick driver（避免 DU 持續打 PathSolver 跟 Coverage 搶 GPU）
- compute 完成後恢復 DU tick
"""
from datetime import datetime, timezone

import requests
from rest_framework.decorators import api_view

from main.apps.ran_signal.serializers.coverage_serializers import (
    CoverageMapRequestSerializer,
    CoverageMapResponseSerializer,
)
from main.apps.ran_signal.services.business.sionna_operations import SionnaBusinessService
from main.apps.ran_signal.services.common.timestamp_service import TimestampService
from main.utils.env_loader import get_str
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


logger = get_logger(__name__)


def _du_url(element: str) -> str:
    host = get_str("HTTP_DU_HOST", "du")
    port = get_str("HTTP_DU_PORT", "8000")
    return f"http://{host}:{port}/api/v0.1/DU/Tick/TickController/{element}"


def _pause_du_tick() -> bool:
    """暫停 DU 背景 tick（讓 Coverage 獨佔 GPU）。回傳「先前是否在跑」。"""
    try:
        r = requests.post(_du_url("read"), json={}, timeout=3)
        was_running = bool(r.json().get("data", {}).get("is_running", False))
    except Exception as exc:
        logger.warning("CoverageActor: cannot read DU tick state: %s", exc)
        return False
    if was_running:
        try:
            requests.post(_du_url("stop"), json={}, timeout=3)
            logger.info("CoverageActor: paused DU tick driver")
        except Exception as exc:
            logger.warning("CoverageActor: failed to stop DU tick: %s", exc)
            return False
    return was_running


def _resume_du_tick() -> None:
    try:
        requests.post(_du_url("start"), json={}, timeout=3)
        logger.info("CoverageActor: resumed DU tick driver")
    except Exception as exc:
        logger.warning("CoverageActor: failed to resume DU tick: %s", exc)


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

        # 暫停 DU tick：避免 Coverage 跟 PathSolver 互搶 GPU
        du_was_running = _pause_du_tick()

        started_ms = TimestampService.now_ms()
        try:
            result = SionnaBusinessService.compute_coverage(
                grid=validated["grid"],
                include_sinr=validated["include_sinr"],
                max_depth=validated["max_depth"],
                null_threshold_dbm=validated["null_threshold_dbm"],
                diffraction=validated["diffraction"],
                diffuse_reflection=validated["diffuse_reflection"],
            )
        except MemoryError:
            logger.error("GPU OOM on coverage_map")
            if du_was_running:
                _resume_du_tick()
            return error_response("GPU out of memory for coverage grid", http_status=503)
        except RuntimeError as exc:
            logger.exception("Coverage compute RuntimeError")
            if du_was_running:
                _resume_du_tick()
            return error_response(str(exc), http_status=500)
        finally:
            # 不論成敗都恢復 DU tick（成功路徑也要走到這），確保 stream 不卡死
            pass

        # Coverage 完成 → 恢復 DU tick
        if du_was_running:
            _resume_du_tick()

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
