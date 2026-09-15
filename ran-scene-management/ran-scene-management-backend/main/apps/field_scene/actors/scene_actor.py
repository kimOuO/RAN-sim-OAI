"""Scene actors — Controller(create/update/delete)+ Reader(read)。全 POST(backend_rule §7-2)。"""
from __future__ import annotations

import json

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.field_scene.models.scene import Scene
from main.apps.field_scene.serializers.scene_serializers import SceneReadSerializer, SceneWriteSerializer
from main.apps.field_scene.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.field_scene.services.common.timestamp_service import TimestampService
from main.apps.field_scene.services.common.uuid_service import UUIDService
from main.apps.field_scene.services.optional.scene_tree.scene_tree import build_scene_tree
from main.apps.simulation_run.models.scene_run import SceneRun
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)
UUID_FIELD = "scene_uuid"


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


class SceneController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def create(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        ser = SceneWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        now = TimestampService.get_current_timestamp()
        data = {UUID_FIELD: UUIDService.generate_uuid("scene"), "scene_created_at": now, "scene_updated_at": now, **ser.validated_data}
        entity = SqlDbBusinessService.create_entity(Scene, data)
        logger.info("scene created %s", getattr(entity, UUID_FIELD))
        return success_response(SceneReadSerializer(entity).data, "created", 201)

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
        entity = SqlDbBusinessService.get_or_none(Scene, UUID_FIELD, uid)
        if entity is None:
            return error_response("Not found", uid, 404)
        ser = SceneWriteSerializer(entity, data=payload, partial=True)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        data = {**ser.validated_data, "scene_updated_at": TimestampService.get_current_timestamp()}
        entity = SqlDbBusinessService.update_entity(Scene, UUID_FIELD, uid, data)
        return success_response(SceneReadSerializer(entity).data, "updated", 200)

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
        n = SqlDbBusinessService.delete_entity(Scene, UUID_FIELD, uid)
        if n == 0:
            return error_response("Not found", uid, 404)
        return success_response({"deleted": n}, "deleted", 200)


class SceneReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        """body 有 scene_uuid → 單筆;f_<parent>_uuid / 任一欄位 → 過濾列表;空 → 全部。"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        if UUID_FIELD in payload:
            entity = SqlDbBusinessService.get_or_none(Scene, UUID_FIELD, payload[UUID_FIELD])
            if entity is None:
                return error_response("Not found", payload[UUID_FIELD], 404)
            return success_response(SceneReadSerializer(entity).data, "ok", 200)
        filters = {}
        for k, v in payload.items():
            if k.startswith("f_") and k.endswith("_uuid"):
                # f_<fk_field>_uuid → <fk_field>__<parent_table>_uuid(用 model 元資料解析,支援同表多 FK)
                fk_name = k[2:-5]
                try:
                    fk = Scene._meta.get_field(fk_name)
                    filters[f"{fk_name}__{fk.target_field.name}"] = v
                except Exception:  # noqa: BLE001
                    filters[k] = v
            else:
                filters[k] = v
        qs = SqlDbBusinessService.list_entities(Scene, **filters)
        return success_response(SceneReadSerializer(qs, many=True).data, "ok", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read_full_tree(request):
        """body {scene_uuid} 或 {scene_run_uuid} → 整棵樹(見 scene_tree.build_scene_tree)。"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        run = None
        if payload.get("scene_run_uuid"):
            run = SqlDbBusinessService.get_or_none(SceneRun, "scene_run_uuid", payload["scene_run_uuid"])
            if run is None:
                return error_response("Not found", payload["scene_run_uuid"], 404)
            scene = run.scene
        elif payload.get("scene_uuid"):
            scene = SqlDbBusinessService.get_or_none(Scene, UUID_FIELD, payload["scene_uuid"])
            if scene is None:
                return error_response("Not found", payload["scene_uuid"], 404)
        else:
            return error_response("Validation failed", {"scene_uuid|scene_run_uuid": "required"}, 400)
        return success_response(build_scene_tree(scene, run), "ok", 200)
