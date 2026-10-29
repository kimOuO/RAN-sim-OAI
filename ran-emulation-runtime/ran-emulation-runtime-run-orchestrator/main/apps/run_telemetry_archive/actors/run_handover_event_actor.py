"""RunHandoverEvent actors — Controller(create/update/delete)+ Reader(read)。全 POST(backend_rule §7-2)。"""
from __future__ import annotations

import json

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.run_telemetry_archive.models.run_handover_event import RunHandoverEvent
from main.apps.run_telemetry_archive.serializers.run_handover_event_serializers import RunHandoverEventReadSerializer, RunHandoverEventWriteSerializer
from main.apps.run_telemetry_archive.services.business.run_seq_filter import apply_run_seq
from main.apps.run_telemetry_archive.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.run_telemetry_archive.services.common.timestamp_service import TimestampService
from main.apps.run_telemetry_archive.services.common.uuid_service import UUIDService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)
UUID_FIELD = "run_handover_event_uuid"


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


class RunHandoverEventController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def create(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        ser = RunHandoverEventWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        now = TimestampService.get_current_timestamp()
        data = {UUID_FIELD: UUIDService.generate_uuid("run_handover_event"), "run_handover_event_created_at": now, "run_handover_event_updated_at": now, **ser.validated_data}
        entity = SqlDbBusinessService.create_entity(RunHandoverEvent, data)
        logger.info("run_handover_event created %s", getattr(entity, UUID_FIELD))
        return success_response(RunHandoverEventReadSerializer(entity).data, "created", 201)

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
        entity = SqlDbBusinessService.get_or_none(RunHandoverEvent, UUID_FIELD, uid)
        if entity is None:
            return error_response("Not found", uid, 404)
        ser = RunHandoverEventWriteSerializer(entity, data=payload, partial=True)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        data = {**ser.validated_data, "run_handover_event_updated_at": TimestampService.get_current_timestamp()}
        entity = SqlDbBusinessService.update_entity(RunHandoverEvent, UUID_FIELD, uid, data)
        return success_response(RunHandoverEventReadSerializer(entity).data, "updated", 200)

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
        n = SqlDbBusinessService.delete_entity(RunHandoverEvent, UUID_FIELD, uid)
        if n == 0:
            return error_response("Not found", uid, 404)
        return success_response({"deleted": n}, "deleted", 200)


class RunHandoverEventReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        """body 有 run_handover_event_uuid → 單筆;f_<parent>_uuid / 任一欄位 → 過濾列表;空 → 全部。"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        if UUID_FIELD in payload:
            entity = SqlDbBusinessService.get_or_none(RunHandoverEvent, UUID_FIELD, payload[UUID_FIELD])
            if entity is None:
                return error_response("Not found", payload[UUID_FIELD], 404)
            return success_response(RunHandoverEventReadSerializer(entity).data, "ok", 200)
        try:
            limit = int(payload.pop("limit", 5000))
            after_id = int(payload.pop("after_id", 0) or 0)
            run_seq = payload.pop("run_seq", None)
            run_seq = None if run_seq is None else int(run_seq)
        except (TypeError, ValueError):
            return error_response("Validation failed", {"limit": "must be int", "after_id": "must be int"}, 400)
        filters = {}
        for k, v in payload.items():
            if k.startswith("f_") and k.endswith("_uuid"):
                # f_<fk_field>_uuid → <fk_field>__<parent_table>_uuid(用 model 元資料解析,支援同表多 FK)
                fk_name = k[2:-5]
                try:
                    fk = RunHandoverEvent._meta.get_field(fk_name)
                    filters[f"{fk_name}__{fk.target_field.name}"] = v
                except Exception:  # noqa: BLE001
                    filters[k] = v
            else:
                filters[k] = v
        qs = SqlDbBusinessService.list_entities(RunHandoverEvent, **filters)
        qs = apply_run_seq(qs, RunHandoverEvent, filters.get("f_scene_run_uuid"), run_seq)
        # 2026-09-17:以前整張回(長跑 run 有數萬筆、2 MB+,監控頁每 3 秒拉一次)→ 預設最近 5000 筆 + 增量
        if after_id:
            qs = qs.filter(id__gt=after_id)
        if limit > 0:
            recent = list(qs.order_by("-id")[:limit]); recent.reverse()
            return success_response(RunHandoverEventReadSerializer(recent, many=True).data, "ok", 200)
        return success_response(RunHandoverEventReadSerializer(qs.order_by("id"), many=True).data, "ok", 200)
