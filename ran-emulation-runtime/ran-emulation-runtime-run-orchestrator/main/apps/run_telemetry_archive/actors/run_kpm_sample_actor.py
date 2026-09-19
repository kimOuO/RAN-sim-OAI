"""RunKpmSample actors — Controller(create/update/delete)+ Reader(read)。全 POST(backend_rule §7-2)。"""
from __future__ import annotations

import json

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.run_telemetry_archive.models.run_kpm_sample import RunKpmSample
from main.apps.run_telemetry_archive.serializers.run_kpm_sample_serializers import RunKpmSampleReadSerializer, RunKpmSampleWriteSerializer
from main.apps.run_telemetry_archive.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.run_telemetry_archive.services.common.timestamp_service import TimestampService
from main.apps.run_telemetry_archive.services.common.uuid_service import UUIDService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)
UUID_FIELD = "run_kpm_sample_uuid"


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


class RunKpmSampleController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def create(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        ser = RunKpmSampleWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        now = TimestampService.get_current_timestamp()
        data = {UUID_FIELD: UUIDService.generate_uuid("run_kpm_sample"), "run_kpm_sample_created_at": now, "run_kpm_sample_updated_at": now, **ser.validated_data}
        entity = SqlDbBusinessService.create_entity(RunKpmSample, data)
        logger.info("run_kpm_sample created %s", getattr(entity, UUID_FIELD))
        return success_response(RunKpmSampleReadSerializer(entity).data, "created", 201)

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
        entity = SqlDbBusinessService.get_or_none(RunKpmSample, UUID_FIELD, uid)
        if entity is None:
            return error_response("Not found", uid, 404)
        ser = RunKpmSampleWriteSerializer(entity, data=payload, partial=True)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        data = {**ser.validated_data, "run_kpm_sample_updated_at": TimestampService.get_current_timestamp()}
        entity = SqlDbBusinessService.update_entity(RunKpmSample, UUID_FIELD, uid, data)
        return success_response(RunKpmSampleReadSerializer(entity).data, "updated", 200)

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
        n = SqlDbBusinessService.delete_entity(RunKpmSample, UUID_FIELD, uid)
        if n == 0:
            return error_response("Not found", uid, 404)
        return success_response({"deleted": n}, "deleted", 200)


_DEFAULT_LIMIT = 3600   # 1 視窗 = 1 s sim-time → 預設最多一小時


class RunKpmSampleReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        """body 有 run_kpm_sample_uuid → 單筆;f_<parent>_uuid / 任一欄位 → 過濾列表;空 → 全部。"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        if UUID_FIELD in payload:
            entity = SqlDbBusinessService.get_or_none(RunKpmSample, UUID_FIELD, payload[UUID_FIELD])
            if entity is None:
                return error_response("Not found", payload[UUID_FIELD], 404)
            return success_response(RunKpmSampleReadSerializer(entity).data, "ok", 200)
        # 2026-09-16:以前一次回傳全部 —— 長跑的 run 累積到 30 萬筆,單次請求 > 30 s,
        # 監控頁每 3 秒輪詢就讓 orchestrator 反覆組數百 MB 的回應。改成預設只回最近 limit 筆
        # (依建立時間),limit=0 才明確要全部。回傳仍依時間由舊到新。
        try:
            limit = int(payload.pop("limit", _DEFAULT_LIMIT))
            after_id = int(payload.pop("after_id", 0) or 0)   # 2026-09-17:增量輪詢,只回 id > after_id
            # 2026-09-19:同一 run uuid 多次執行的資料混在同一張表,查詢極易誤判(實際踩過)。
            # 預設只回**最近一次執行**;run_seq=<n> 指定某一次,run_seq=0 才是全部。
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
                    fk = RunKpmSample._meta.get_field(fk_name)
                    filters[f"{fk_name}__{fk.target_field.name}"] = v
                except Exception:  # noqa: BLE001
                    filters[k] = v
            else:
                filters[k] = v
        qs = SqlDbBusinessService.list_entities(RunKpmSample, **filters)
        run_uuid = filters.get("f_scene_run_uuid")
        if run_seq is None and run_uuid:          # 預設:最近一次執行
            from django.db.models import Max
            latest = RunKpmSample.objects.filter(f_scene_run_uuid=run_uuid).aggregate(m=Max("run_seq")).get("m")
            if latest:
                qs = qs.filter(run_seq=latest)
        elif run_seq:                              # 指定某一次(0 = 不過濾,全部)
            qs = qs.filter(run_seq=run_seq)
        if after_id:
            qs = qs.filter(id__gt=after_id)
        if limit > 0:
            recent = list(qs.order_by("-id")[:limit])   # id 與寫入順序一致,走主鍵索引
            recent.reverse()
            return success_response(RunKpmSampleReadSerializer(recent, many=True).data, "ok", 200)
        return success_response(RunKpmSampleReadSerializer(qs.order_by("id"), many=True).data, "ok", 200)
