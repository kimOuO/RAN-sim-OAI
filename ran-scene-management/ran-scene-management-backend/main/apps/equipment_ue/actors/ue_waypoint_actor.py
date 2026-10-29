"""UeWaypoint actors — Controller(create/update/delete)+ Reader(read)。全 POST(backend_rule §7-2)。"""
from __future__ import annotations

import json
import math

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.equipment_ue.models.ue_waypoint import UeWaypoint
from main.apps.equipment_ue.serializers.ue_waypoint_serializers import UeWaypointReadSerializer, UeWaypointWriteSerializer
from main.apps.equipment_ue.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.equipment_ue.services.common.timestamp_service import TimestampService
from main.apps.equipment_ue.services.common.uuid_service import UUIDService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)
UUID_FIELD = "ue_waypoint_uuid"


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


class UeWaypointController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def replace(request):
        """Replace one UE's complete path atomically after validating all points."""
        from main.apps.equipment_ue.models.ue import Ue
        try:
            payload = _body(request)
            points = payload.get("waypoints")
            if not isinstance(points, list) or not points or len(points) > 10000:
                raise ValueError("waypoints must contain 1–10000 [t,x,y,z] points")
            normalized = []
            for i, point in enumerate(points):
                if not isinstance(point, list) or len(point) != 4 or any(isinstance(v, bool) for v in point):
                    raise ValueError(f"waypoint {i + 1}: expected [t,x,y,z]")
                values = [float(v) for v in point]
                if not all(math.isfinite(v) for v in values) or values[0] < 0:
                    raise ValueError(f"waypoint {i + 1}: values must be finite and time >= 0")
                if (i == 0 and values[0] != 0) or (i > 0 and values[0] <= normalized[-1][0]):
                    raise ValueError("first time must be 0; subsequent times must strictly increase")
                normalized.append(values)
        except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as exc:
            return error_response("Validation failed", str(exc), 400)
        ue = Ue.objects.select_for_update().filter(ue_uuid=payload.get("f_ue_uuid")).first()
        if ue is None:
            return error_response("UE not found", payload.get("f_ue_uuid"), 404)
        now = TimestampService.get_current_timestamp()
        rows = [UeWaypoint(ue=ue, ue_waypoint_uuid=UUIDService.generate_uuid("ue_waypoint"),
                           ord=i, t_sec=p[0], x=p[1], y=p[2], z=p[3],
                           ue_waypoint_created_at=now, ue_waypoint_updated_at=now)
                for i, p in enumerate(normalized)]
        UeWaypoint.objects.filter(ue=ue).delete()
        UeWaypoint.objects.bulk_create(rows)
        return success_response(UeWaypointReadSerializer(rows, many=True).data, "path saved", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def create(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        ser = UeWaypointWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        now = TimestampService.get_current_timestamp()
        data = {UUID_FIELD: UUIDService.generate_uuid("ue_waypoint"), "ue_waypoint_created_at": now, "ue_waypoint_updated_at": now, **ser.validated_data}
        entity = SqlDbBusinessService.create_entity(UeWaypoint, data)
        logger.info("ue_waypoint created %s", getattr(entity, UUID_FIELD))
        return success_response(UeWaypointReadSerializer(entity).data, "created", 201)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def update(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        uid = payload.pop(UUID_FIELD, None)
        if not uid:
            return error_response("Validation failed", {UUID_FIELD: "required"}, 400)
        entity = SqlDbBusinessService.get_or_none(UeWaypoint, UUID_FIELD, uid)
        if entity is None:
            return error_response("Not found", uid, 404)
        ser = UeWaypointWriteSerializer(entity, data=payload, partial=True)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        data = {**ser.validated_data, "ue_waypoint_updated_at": TimestampService.get_current_timestamp()}
        entity = SqlDbBusinessService.update_entity(UeWaypoint, UUID_FIELD, uid, data)
        return success_response(UeWaypointReadSerializer(entity).data, "updated", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def delete(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        uid = payload.get(UUID_FIELD)
        if not uid:
            return error_response("Validation failed", {UUID_FIELD: "required"}, 400)
        n = SqlDbBusinessService.delete_entity(UeWaypoint, UUID_FIELD, uid)
        if n == 0:
            return error_response("Not found", uid, 404)
        return success_response({"deleted": n}, "deleted", 200)


class UeWaypointReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        """body 有 ue_waypoint_uuid → 單筆;f_<parent>_uuid / 任一欄位 → 過濾列表;空 → 全部。"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        if UUID_FIELD in payload:
            entity = SqlDbBusinessService.get_or_none(UeWaypoint, UUID_FIELD, payload[UUID_FIELD])
            if entity is None:
                return error_response("Not found", payload[UUID_FIELD], 404)
            return success_response(UeWaypointReadSerializer(entity).data, "ok", 200)
        filters = {}
        for k, v in payload.items():
            if k.startswith("f_") and k.endswith("_uuid"):
                # f_<fk_field>_uuid → <fk_field>__<parent_table>_uuid(用 model 元資料解析,支援同表多 FK)
                fk_name = k[2:-5]
                try:
                    fk = UeWaypoint._meta.get_field(fk_name)
                    filters[f"{fk_name}__{fk.target_field.name}"] = v
                except Exception:  # noqa: BLE001
                    filters[k] = v
            else:
                filters[k] = v
        qs = SqlDbBusinessService.list_entities(UeWaypoint, **filters)
        return success_response(UeWaypointReadSerializer(qs, many=True).data, "ok", 200)
