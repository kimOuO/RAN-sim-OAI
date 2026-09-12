"""ConfigActor — 查/重載/覆蓋/回復 配置。"""
from rest_framework.decorators import api_view

from main.apps.ran_signal.serializers.config_serializers import (
    ConfigReadSerializer,
    ConfigReloadRequestSerializer,
    PushSceneRequestSerializer,
    PushSceneResponseSerializer,
)
from main.apps.ran_signal.services.business.sionna_operations import SionnaBusinessService
from main.apps.ran_signal.services.optional.ran_calculation.scene_frequency import (
    SceneFrequencyMismatch,
)
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


logger = get_logger(__name__)


class ConfigActor:
    @staticmethod
    @api_view(["POST"])
    def read(request):
        config = SionnaBusinessService.get_loaded_config()
        if config is None:
            return error_response("No scene loaded yet", http_status=503)
        ser = ConfigReadSerializer(config)
        return success_response(ser.data, "OK")

    @staticmethod
    @api_view(["POST"])
    def reload(request):
        """從 scene_config.json 重新載入預設（等同 reset_to_default）。"""
        req_ser = ConfigReloadRequestSerializer(data=request.data)
        if not req_ser.is_valid():
            return error_response("Invalid request", errors=req_ser.errors, http_status=400)

        try:
            config = SionnaBusinessService.reload_scene_config()
        except SceneFrequencyMismatch as exc:
            logger.warning("Reload rejected: %s", exc)
            return error_response(str(exc), http_status=400)
        except FileNotFoundError as exc:
            return error_response(f"scene_config.json not found: {exc}", http_status=500)
        except Exception as exc:
            logger.exception("Reload failed")
            return error_response(f"Reload failed: {exc}", http_status=500)

        ser = ConfigReadSerializer(config)
        return success_response(ser.data, "Reloaded")

    @staticmethod
    @api_view(["POST"])
    def push_scene(request):
        """Layer 2 override：外部平台（如 Omniverse）送真實場景覆蓋預設。

        payload 結構參考 PushSceneRequestSerializer。
        override_mode:
          - full         : geometry + gnbs 都換（ues 可選）
          - ran_only     : 只換 gnbs / ues，場景幾何保留
          - geometry_only: 只換 Mitsuba XML，gnbs/ues 保留
        """
        req_ser = PushSceneRequestSerializer(data=request.data)
        if not req_ser.is_valid():
            return error_response("Validation failed", errors=req_ser.errors, http_status=400)

        payload = req_ser.validated_data
        logger.info(
            "push_scene: scene_id=%s mode=%s gnbs=%d ues=%d ttl=%s",
            payload["scene_id"],
            payload.get("override_mode", "full"),
            len(payload.get("gnbs") or []),
            len(payload.get("ues") or []),
            payload.get("ttl_seconds"),
        )

        try:
            result = SionnaBusinessService.apply_override(payload)
        except SceneFrequencyMismatch as exc:
            logger.warning("apply_override rejected: %s", exc)
            return error_response(str(exc), http_status=400)
        except RuntimeError as exc:
            logger.exception("apply_override failed")
            return error_response(str(exc), http_status=400)
        except Exception as exc:
            logger.exception("apply_override unexpected error")
            return error_response(f"Internal error: {exc}", http_status=500)

        resp_ser = PushSceneResponseSerializer(result)
        return success_response(resp_ser.data, "Scene override applied")

    @staticmethod
    @api_view(["POST"])
    def reset_to_default(request):
        """退回 scene_config.json 預設（取消 runtime override）。"""
        try:
            config = SionnaBusinessService.reset_to_default()
        except Exception as exc:
            logger.exception("reset_to_default failed")
            return error_response(f"Reset failed: {exc}", http_status=500)

        ser = ConfigReadSerializer(config)
        return success_response(ser.data, "Reset to default")
