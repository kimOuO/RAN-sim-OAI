"""Cell actors — Controller(create/update/delete)+ Reader(read)。全 POST(backend_rule §7-2)。"""
from __future__ import annotations

import json

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.equipment_ran.models.cell import Cell
from main.apps.equipment_ran.serializers.cell_serializers import CellReadSerializer, CellWriteSerializer
from main.apps.equipment_ran.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.equipment_ran.services.common.timestamp_service import TimestampService
from main.apps.equipment_ran.services.common.uuid_service import UUIDService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)
UUID_FIELD = "cell_uuid"


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


class CellController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def create(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        ser = CellWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        now = TimestampService.get_current_timestamp()
        data = {UUID_FIELD: UUIDService.generate_uuid("cell"), "cell_created_at": now, "cell_updated_at": now, **ser.validated_data}
        # 多 gNB(2026-09-27):local_cell_id 在同一個 gNB(跨它所有 DU)內唯一,決定 NCI 的低 14 bit。
        gnb_uuid = data["du"].gnb_id
        used = set(Cell.objects.filter(du__gnb_id=gnb_uuid).values_list("local_cell_id", flat=True))
        if data.get("local_cell_id") is None:
            data["local_cell_id"] = next(i for i in range(1 << 14) if i not in used)
        elif not 0 <= int(data["local_cell_id"]) < (1 << 14) or data["local_cell_id"] in used:
            return error_response("Validation failed", {"local_cell_id": "必須在 0–16383 且在同一 gNB 內唯一"}, 400)
        entity = SqlDbBusinessService.create_entity(Cell, data)
        logger.info("cell created %s", getattr(entity, UUID_FIELD))
        return success_response(CellReadSerializer(entity).data, "created", 201)

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
        entity = SqlDbBusinessService.get_or_none(Cell, UUID_FIELD, uid)
        if entity is None:
            return error_response("Not found", uid, 404)
        ser = CellWriteSerializer(entity, data=payload, partial=True)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        data = {**ser.validated_data, "cell_updated_at": TimestampService.get_current_timestamp()}
        entity = SqlDbBusinessService.update_entity(Cell, UUID_FIELD, uid, data)
        return success_response(CellReadSerializer(entity).data, "updated", 200)

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
        n = SqlDbBusinessService.delete_entity(Cell, UUID_FIELD, uid)
        if n == 0:
            return error_response("Not found", uid, 404)
        return success_response({"deleted": n}, "deleted", 200)


class CellReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        """body 有 cell_uuid → 單筆;f_<parent>_uuid / 任一欄位 → 過濾列表;空 → 全部。"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        if UUID_FIELD in payload:
            entity = SqlDbBusinessService.get_or_none(Cell, UUID_FIELD, payload[UUID_FIELD])
            if entity is None:
                return error_response("Not found", payload[UUID_FIELD], 404)
            return success_response(CellReadSerializer(entity).data, "ok", 200)
        filters = {}
        for k, v in payload.items():
            if k.startswith("f_") and k.endswith("_uuid"):
                # f_<fk_field>_uuid → <fk_field>__<parent_table>_uuid(用 model 元資料解析,支援同表多 FK)
                fk_name = k[2:-5]
                try:
                    fk = Cell._meta.get_field(fk_name)
                    filters[f"{fk_name}__{fk.target_field.name}"] = v
                except Exception:  # noqa: BLE001
                    filters[k] = v
            else:
                filters[k] = v
        qs = SqlDbBusinessService.list_entities(Cell, **filters)
        return success_response(CellReadSerializer(qs, many=True).data, "ok", 200)
