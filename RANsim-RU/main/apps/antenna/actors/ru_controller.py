"""RuController — backend_rule §13：Actor 處理 HTTP + 編排業務。

Endpoints:
  POST /api/v0.1/RU/Config/RuController/update_antenna
  POST /api/v0.1/RU/Config/RuController/update_cells
  POST /api/v0.1/RU/Config/RuController/update_ues
"""
import json

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.antenna.models.antenna_config import AntennaConfig
from main.apps.antenna.models.cell import Cell
from main.apps.antenna.models.ue_position import UePosition
from main.apps.antenna.serializers.antenna_serializers import (
    AntennaConfigReadSerializer,
    AntennaConfigWriteSerializer,
)
from main.apps.antenna.serializers.cell_serializers import (
    CellListWriteSerializer,
    CellReadSerializer,
)
from main.apps.antenna.serializers.ue_position_serializers import (
    UePositionListWriteSerializer,
    UePositionReadSerializer,
)
from main.apps.antenna.services.business.relational_db import SqlDbBusinessService
from main.apps.antenna.services.common.timestamp_service import TimestampService
from main.apps.antenna.services.common.uuid_service import UUIDService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


logger = get_logger(__name__)


def _parse_body(request):
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


class RuController:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def update_antenna(request):
        try:
            payload = _parse_body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)

        ser = AntennaConfigWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)

        validated = ser.validated_data
        now = TimestampService.get_current_timestamp()
        uuid = UUIDService.generate_uuid("antenna", "")  # 一律新建一筆，取 latest

        entity_data = {
            "antenna_config_uuid": uuid,
            "antenna_config_created_at": now,
            "antenna_config_updated_at": now,
            **validated,
        }
        entity = SqlDbBusinessService.create_entity(AntennaConfig, entity_data)
        logger.info("update_antenna ok: %s rows=%d cols=%d %s/%s",
                    uuid, validated["rows"], validated["cols"],
                    validated["polarization"], validated["pattern"])

        return success_response(AntennaConfigReadSerializer(entity).data, "antenna config updated", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def update_cells(request):
        try:
            payload = _parse_body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)

        ser = CellListWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)

        cells_in = ser.validated_data["cells"]
        now = TimestampService.get_current_timestamp()

        # 全量替換策略：先清掉沒在這次列表的 cell，再 upsert 提交的
        incoming_names = [c["name"] for c in cells_in]
        SqlDbBusinessService.filter_entities(Cell).exclude(name__in=incoming_names).delete()

        result = []
        for c in cells_in:
            uuid = UUIDService.generate_uuid("cell", c["name"])
            defaults = {
                "cell_uuid": uuid,
                "pci": c["pci"],
                "azimuth_deg": c["azimuth_deg"],
                "position_x": c["position"]["x"],
                "position_y": c["position"]["y"],
                "position_z": c["position"]["z"],
                "frequency_ghz": c["frequency_ghz"],
                "bandwidth_mhz": c["bandwidth_mhz"],
                "cell_updated_at": now,
                "cell_created_at": now,
            }
            obj = SqlDbBusinessService.upsert_entity(Cell, lookup={"name": c["name"]}, defaults=defaults)
            result.append(obj)

        logger.info("update_cells ok: %d cells", len(result))
        return success_response(
            CellReadSerializer(result, many=True).data,
            f"updated {len(result)} cells",
            200,
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def update_ues(request):
        try:
            payload = _parse_body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)

        ser = UePositionListWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)

        ues_in = ser.validated_data["ues"]
        now = TimestampService.get_current_timestamp()

        result = []
        for u in ues_in:
            uuid = UUIDService.generate_uuid("ue", u["id"])
            velocity = u.get("velocity") or {"x": 0.0, "y": 0.0, "z": 0.0}
            defaults = {
                "ue_position_uuid": uuid,
                "position_x": u["position"]["x"],
                "position_y": u["position"]["y"],
                "position_z": u["position"]["z"],
                "velocity_x": velocity["x"],
                "velocity_y": velocity["y"],
                "velocity_z": velocity["z"],
                "ue_position_updated_at": now,
                "ue_position_created_at": now,
            }
            obj = SqlDbBusinessService.upsert_entity(
                UePosition, lookup={"ue_id": u["id"]}, defaults=defaults,
            )
            result.append(obj)

        logger.info("update_ues ok: %d UEs", len(result))
        return success_response(
            UePositionReadSerializer(result, many=True).data,
            f"updated {len(result)} ues",
            200,
        )
