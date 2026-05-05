"""SimLoopActor — 模擬 loop 控制（setup / start / stop / status）。"""
from rest_framework.decorators import api_view

from main.apps.ran_signal.serializers.sim_loop_serializers import (
    SimLoopSetupRequestSerializer,
    SimLoopSetupResponseSerializer,
    SimLoopStartResponseSerializer,
    SimLoopStopResponseSerializer,
    SimLoopStatusResponseSerializer,
)
from main.apps.ran_signal.services.business.sim_loop_service import SimLoopService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


logger = get_logger(__name__)


class SimLoopActor:
    """模擬 loop 控制。"""

    @staticmethod
    @api_view(["POST"])
    def setup(request):
        """設定 UE 軌跡（不啟動 loop）。

        Args:
            request.data: {
                ues: [
                    {
                        name: str,
                        waypoints: [[x,y,z], [x,y,z], ...],
                        speed_mps: float,
                        loop: bool (optional, default=True)
                    }
                ]
            }

        Returns:
            {ues_configured: int, total_duration_ms: float}
        """
        # 過濾掉無效的 UE（waypoints < 2）
        data = dict(request.data)
        ues_input = data.get("ues", [])
        valid_ues = [ue for ue in ues_input if ue.get("waypoints") and len(ue.get("waypoints", [])) >= 2]
        data["ues"] = valid_ues

        req_ser = SimLoopSetupRequestSerializer(data=data)
        if not req_ser.is_valid():
            return error_response(
                "Invalid setup request",
                errors=req_ser.errors,
                http_status=400,
            )

        validated = req_ser.validated_data
        ues = validated.get("ues", [])

        logger.info("SimLoopActor.setup ues=%d", len(ues))

        try:
            result = SimLoopService.setup(
                session_uuid=SimLoopService._session_uuid,
                scene_id=SimLoopService._scene_id,
                ues=ues,
            )
            resp_ser = SimLoopSetupResponseSerializer(result)
            return success_response(resp_ser.data, message="UE trajectories configured")
        except Exception as e:
            logger.exception("Setup failed")
            return error_response(f"Setup failed: {e}", http_status=500)

    @staticmethod
    @api_view(["POST"])
    def start(request):
        """啟動模擬 loop。

        Returns:
            {status: str, session_uuid: str, tick_count: int}
        """
        logger.info("SimLoopActor.start")

        try:
            result = SimLoopService.start()
            if result.get("status") == "error":
                return error_response(result.get("message", "Unknown error"), http_status=400)
            resp_ser = SimLoopStartResponseSerializer(result)
            return success_response(resp_ser.data, message="Simulation started")
        except Exception as e:
            logger.exception("Start failed")
            return error_response(f"Start failed: {e}", http_status=500)

    @staticmethod
    @api_view(["POST"])
    def stop(request):
        """停止模擬 loop 並通知 Omniverse。

        Returns:
            {status: str, session_uuid: str, tick_count: int, elapsed_ms: float}
        """
        logger.info("SimLoopActor.stop")

        try:
            result = SimLoopService.stop()
            resp_ser = SimLoopStopResponseSerializer(result)
            return success_response(resp_ser.data, message="Simulation stopped")
        except Exception as e:
            logger.exception("Stop failed")
            return error_response(f"Stop failed: {e}", http_status=500)

    @staticmethod
    @api_view(["POST"])
    def status(request):
        """查詢當前狀態。

        Returns:
            {is_running: bool, session_uuid: str, scene_id: str, ue_count: int,
             tick_count: int, started_at_ms: int, elapsed_ms: float}
        """
        try:
            result = SimLoopService.status()
            resp_ser = SimLoopStatusResponseSerializer(result)
            return success_response(resp_ser.data, message="OK")
        except Exception as e:
            logger.exception("Status query failed")
            return error_response(f"Status query failed: {e}", http_status=500)

    @staticmethod
    @api_view(["POST"])
    def ue_positions(request):
        """查詢所有 UE 的當前位置。

        Returns:
            {ue_name: [x, y, z], ...}
        """
        try:
            positions = SimLoopService.get_ue_positions()
            return success_response(positions, message="OK")
        except Exception as e:
            logger.exception("UE positions query failed")
            return error_response(f"UE positions query failed: {e}", http_status=500)
