"""RuController — backend_rule §13：Actor 處理 HTTP + 編排業務。

Endpoints:
  POST /api/v0.1/RU/Config/RuController/update_antenna
  POST /api/v0.1/RU/Config/RuController/update_cells
  POST /api/v0.1/RU/Config/RuController/update_ues
  POST /api/v0.1/RU/Config/RuController/set_channel_mode  (Phase B B.6)
"""
import json
import os

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
        if not cells_in:
            return error_response("cells must not be empty", "use POST with at least 1 cell", 400)

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
                "gnb_id": c.get("gnb_id", ""),
                "power_dbm": c.get("power_dbm", 23.0),
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
        if not ues_in:
            return error_response("ues must not be empty", "use POST with at least 1 ue", 400)

        now = TimestampService.get_current_timestamp()

        # `clear_stale` 預設 True(對齊原行為);scenario_driver 高倍率 per-tick 推位置
        # 時改傳 False 跳過 DELETE,把 18ms/call 壓到 ~3ms。stale 在 scenario start
        # 由 sync_scene_to_scenario 那條 path 清過了。
        clear_stale = bool(payload.get("clear_stale", True))
        if clear_stale:
            incoming_ids = [u["id"] for u in ues_in]
            deleted, _ = SqlDbBusinessService.filter_entities(UePosition).exclude(ue_id__in=incoming_ids).delete()
            if deleted:
                logger.info("update_ues cleared %d stale UEs", deleted)

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

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def set_channel_mode(request):
        """Phase B B.6 — runtime 切 RU channel mode (live / cached) + 載入 cache。

        Body: {"mode": "live" | "cached", "scenario_id": str (cached 時必填)}

        side effects:
          - 設 os.environ RU_CHANNEL_MODE / RU_SCENARIO_ID
          - 若 mode=cached:呼 channel_cache_loader.reload_cache() 即時 load 對應 npz
          - 若 mode=live :singleton 不 reload (下次 dl_tti 自動走 physics path)

        Returns: { mode, scenario_id, loaded, ues, cells, total_ticks }
        """
        try:
            payload = _parse_body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        mode = str(payload.get("mode", "")).lower().strip()
        scenario_id = str(payload.get("scenario_id", "")).strip()
        if mode not in ("live", "cached"):
            return error_response("mode must be 'live' or 'cached'", {}, 400)
        if mode == "cached" and not scenario_id:
            return error_response("mode=cached requires scenario_id", {}, 400)

        os.environ["RU_CHANNEL_MODE"] = mode
        os.environ["RU_SCENARIO_ID"] = scenario_id if mode == "cached" else ""

        from main.apps.fapi_south.services.optional.channel_cache_loader import (
            reload_cache, write_mode_file,
        )
        # 寫 disk file 讓所有 gunicorn worker 看到 mode 改變(不僅 env)
        write_mode_file(mode, scenario_id if mode == "cached" else "")
        info = {
            "mode": mode,
            "scenario_id": os.environ.get("RU_SCENARIO_ID") or "",
            "loaded": False,
            "ues": 0,
            "cells": 0,
            "total_ticks": 0,
        }
        if mode == "cached":
            cache = reload_cache()
            if cache is None:
                return error_response(
                    f"Failed to load channel cache for scenario_id={scenario_id}",
                    {}, 500,
                )
            info.update({
                "loaded": True,
                "ues": len(cache.ue_names),
                "cells": len(cache.cell_names),
                "total_ticks": cache.total_ticks,
            })
        logger.info("set_channel_mode: %s", info)
        return success_response(info, f"channel mode set to {mode}", 200)
