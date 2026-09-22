"""SceneRun actors — Controller(create/update/delete)+ Reader(read)。全 POST(backend_rule §7-2)。"""
from __future__ import annotations

import json

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.simulation_run.models.scene_run import SceneRun
from main.apps.simulation_run.serializers.scene_run_serializers import SceneRunReadSerializer, SceneRunWriteSerializer
from main.apps.simulation_run.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.simulation_run.services.common.timestamp_service import TimestampService
from main.apps.simulation_run.services.common.uuid_service import UUIDService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)
UUID_FIELD = "scene_run_uuid"


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


class SceneRunController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def create(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        ser = SceneRunWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        now = TimestampService.get_current_timestamp()
        # 2026-09-22:一個場景只有一個 run 設定。
        # 建場景、複製、切片、預算各自都會「建一個 run」,疊起來就是同一場景多個 run;
        # 前端與全樹固定取最早那個(往往是沒預算的空殼),Agent 的 I-3 取最近更新的,
        # 兩邊看到的不是同一個 —— 四個走廊場景全中。與其要求每個呼叫端先查再建,
        # 直接在這裡收斂:場景已有 run 就把這次的欄位更新上去、回那一筆。
        scene = ser.validated_data.get("scene")
        existing = SceneRun.objects.filter(scene=scene).order_by("id").first() if scene is not None else None
        if existing is not None:
            fields = {k: v for k, v in ser.validated_data.items() if k != "scene"}
            fields["scene_run_updated_at"] = now
            entity = SqlDbBusinessService.update_entity(SceneRun, UUID_FIELD, getattr(existing, UUID_FIELD), fields)
            logger.info("scene_run reused %s for scene %s (fields=%s)", getattr(entity, UUID_FIELD), getattr(scene, "scene_uuid", scene), sorted(fields))
            return success_response(SceneRunReadSerializer(entity).data, "reused existing run", 200)
        data = {UUID_FIELD: UUIDService.generate_uuid("scene_run"), "scene_run_created_at": now, "scene_run_updated_at": now, **ser.validated_data}
        entity = SqlDbBusinessService.create_entity(SceneRun, data)
        logger.info("scene_run created %s", getattr(entity, UUID_FIELD))
        return success_response(SceneRunReadSerializer(entity).data, "created", 201)

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
        entity = SqlDbBusinessService.get_or_none(SceneRun, UUID_FIELD, uid)
        if entity is None:
            return error_response("Not found", uid, 404)
        ser = SceneRunWriteSerializer(entity, data=payload, partial=True)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        data = {**ser.validated_data, "scene_run_updated_at": TimestampService.get_current_timestamp()}
        entity = SqlDbBusinessService.update_entity(SceneRun, UUID_FIELD, uid, data)
        return success_response(SceneRunReadSerializer(entity).data, "updated", 200)

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
        n = SqlDbBusinessService.delete_entity(SceneRun, UUID_FIELD, uid)
        if n == 0:
            return error_response("Not found", uid, 404)
        return success_response({"deleted": n}, "deleted", 200)


class SceneRunReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        """body 有 scene_run_uuid → 單筆;f_<parent>_uuid / 任一欄位 → 過濾列表;空 → 全部。"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        if UUID_FIELD in payload:
            entity = SqlDbBusinessService.get_or_none(SceneRun, UUID_FIELD, payload[UUID_FIELD])
            if entity is None:
                return error_response("Not found", payload[UUID_FIELD], 404)
            return success_response(SceneRunReadSerializer(entity).data, "ok", 200)
        filters = {}
        for k, v in payload.items():
            if k.startswith("f_") and k.endswith("_uuid"):
                # f_<fk_field>_uuid → <fk_field>__<parent_table>_uuid(用 model 元資料解析,支援同表多 FK)
                fk_name = k[2:-5]
                try:
                    fk = SceneRun._meta.get_field(fk_name)
                    filters[f"{fk_name}__{fk.target_field.name}"] = v
                except Exception:  # noqa: BLE001
                    filters[k] = v
            else:
                filters[k] = v
        qs = SqlDbBusinessService.list_entities(SceneRun, **filters)
        return success_response(SceneRunReadSerializer(qs, many=True).data, "ok", 200)
