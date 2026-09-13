"""LaunchRequest actors — Controller(create/update/delete)+ Reader(read)。全 POST(backend_rule §7-2)。"""
from __future__ import annotations

import json

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.run_lifecycle.models.launch_request import LaunchRequest
from main.apps.run_lifecycle.serializers.launch_request_serializers import LaunchRequestReadSerializer, LaunchRequestWriteSerializer
from main.apps.run_lifecycle.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.run_lifecycle.services.common.timestamp_service import TimestampService
from main.apps.run_lifecycle.services.common.uuid_service import UUIDService
from django.conf import settings

from main.apps.run_lifecycle.services.optional import container_spawner, health_monitor, platform_clients
from main.apps.run_telemetry_archive.services.optional import cu_archiver
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)
UUID_FIELD = "launch_request_uuid"


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


class LaunchRequestController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def create(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        ser = LaunchRequestWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        now = TimestampService.get_current_timestamp()
        data = {UUID_FIELD: UUIDService.generate_uuid("launch_request"), "launch_request_created_at": now, "launch_request_updated_at": now, **ser.validated_data}
        entity = SqlDbBusinessService.create_entity(LaunchRequest, data)
        logger.info("launch_request created %s", getattr(entity, UUID_FIELD))
        return success_response(LaunchRequestReadSerializer(entity).data, "created", 201)

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
        entity = SqlDbBusinessService.get_or_none(LaunchRequest, UUID_FIELD, uid)
        if entity is None:
            return error_response("Not found", uid, 404)
        ser = LaunchRequestWriteSerializer(entity, data=payload, partial=True)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        data = {**ser.validated_data, "launch_request_updated_at": TimestampService.get_current_timestamp()}
        entity = SqlDbBusinessService.update_entity(LaunchRequest, UUID_FIELD, uid, data)
        return success_response(LaunchRequestReadSerializer(entity).data, "updated", 200)

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
        n = SqlDbBusinessService.delete_entity(LaunchRequest, UUID_FIELD, uid)
        if n == 0:
            return error_response("Not found", uid, 404)
        return success_response({"deleted": n}, "deleted", 200)


class LaunchRequestReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        """body 有 launch_request_uuid → 單筆;f_<parent>_uuid / 任一欄位 → 過濾列表;空 → 全部。"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        if UUID_FIELD in payload:
            entity = SqlDbBusinessService.get_or_none(LaunchRequest, UUID_FIELD, payload[UUID_FIELD])
            if entity is None:
                return error_response("Not found", payload[UUID_FIELD], 404)
            return success_response(LaunchRequestReadSerializer(entity).data, "ok", 200)
        filters = {}
        for k, v in payload.items():
            if k.startswith("f_") and k.endswith("_uuid"):
                # f_<fk_field>_uuid → <fk_field>__<parent_table>_uuid(用 model 元資料解析,支援同表多 FK)
                fk_name = k[2:-5]
                try:
                    fk = LaunchRequest._meta.get_field(fk_name)
                    filters[f"{fk_name}__{fk.target_field.name}"] = v
                except Exception:  # noqa: BLE001
                    filters[k] = v
            else:
                filters[k] = v
        qs = SqlDbBusinessService.list_entities(LaunchRequest, **filters)
        return success_response(LaunchRequestReadSerializer(qs, many=True).data, "ok", 200)


class LaunchController:
    """單 run 版(2026-09-13 P2):起/停一個 scene_run。
    P2 階段仍委派既有 UE driver 的 SimController(共用 CU/DU/RU 容器);P4 改為 spawn per-run 容器。"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def start(request):
        """body {scene_run_uuid, speed_x?, sim_dt_ms?}"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        run_uuid = str(payload.get("scene_run_uuid") or "")
        if not run_uuid:
            return error_response("Validation failed", {"scene_run_uuid": "required"}, 400)
        try:
            tree = platform_clients.read_full_tree(run_uuid)
        except Exception as exc:  # noqa: BLE001
            return error_response("registry unreachable or run not found", str(exc), 502)
        if not tree.get("success"):
            return error_response("scene_run not found", run_uuid, 404)
        t = tree["data"]; run = t.get("run") or {}
        problems = []
        if not t.get("gnbs"):
            problems.append("scene has no gnb")
        if not t.get("ues"):
            problems.append("scene has no ue")
        for g in t.get("gnbs") or []:
            for du in g.get("dus") or []:
                for c in du.get("cells") or []:
                    if not c.get("ru"):
                        problems.append(f"cell {c.get('name')} has no ru")
        if problems:
            return error_response("scene incomplete", problems, 400)
        speed_x = float(payload.get("speed_x") or run.get("speed_x") or 1.0)
        sim_dt_ms = int(payload.get("sim_dt_ms") or run.get("sim_dt_ms") or 500)
        now = TimestampService.get_current_timestamp()
        req_row = SqlDbBusinessService.create_entity(LaunchRequest, {
            UUID_FIELD: UUIDService.generate_uuid("launch_request"), "launch_request_created_at": now, "launch_request_updated_at": now,
            "f_scene_run_uuid": run_uuid, "action": "start", "mode": str(run.get("mode") or "cached"), "speed_x": speed_x, "status": "accepted"})
        try:
            ue_host = None; cu_host = None; instances: dict[str, dict] = {}
            if settings.PER_RUN_ENABLED:
                mode = str(run.get("mode") or "cached")
                if mode == "live" and container_spawner.live_run_exists(run_uuid):
                    raise RuntimeError("live 模式同時只允許 1 個 run(Physics/GPU 共用);請用 cached 或先停另一個 live run")
                # 舊的 run_instance 列清掉(重跑)
                for old in platform_clients.list_run_instances(run_uuid):
                    platform_clients.delete_run_instance(old["run_instance_uuid"])
                spawned = container_spawner.spawn(run_uuid, mode)
                for role, info in spawned.items():
                    r = platform_clients.create_run_instance(run_uuid, role, info["container_id"], info["host_port"])
                    instances[role] = {**info, "run_instance_uuid": (r.get("data") or {}).get("run_instance_uuid")}
                health = container_spawner.wait_healthy({r: i["name"] for r, i in instances.items()})
                if not all(health.values()):
                    raise RuntimeError(f"per-run 容器未就緒: {health}")
                ue_host = instances["ue"]["name"]; cu_host = instances["cu"]["name"]
                health_monitor.start_monitor(run_uuid, instances)
            ue = platform_clients.ue_start(run_uuid, speed_x, sim_dt_ms, host=ue_host)
            ok = bool(ue.get("success"))
            SqlDbBusinessService.update_entity(LaunchRequest, UUID_FIELD, getattr(req_row, UUID_FIELD),
                                               {"status": "started" if ok else "failed", "detail": ue, "launch_request_updated_at": TimestampService.get_current_timestamp()})
            if ok:
                platform_clients.update_scene_run(run_uuid, status="running", speed_x=speed_x, sim_dt_ms=sim_dt_ms, started_at=now.isoformat())
                cu_archiver.start_archiver(run_uuid, sim_dt_ms, cu_host=cu_host)   # P2-3:run 期間封存 CU 落地表(P4-1:per-run CU)
            else:
                platform_clients.update_scene_run(run_uuid, status="failed", notes=str(ue.get("message") or "")[:500])
                return error_response("UE driver refused start", ue, 502)
        except Exception as exc:  # noqa: BLE001
            logger.exception("launch start failed run=%s", run_uuid)
            if settings.PER_RUN_ENABLED:
                health_monitor.stop_monitor(run_uuid)
                try:
                    container_spawner.teardown(run_uuid)
                except Exception:  # noqa: BLE001
                    logger.exception("teardown after failed start %s", run_uuid)
            SqlDbBusinessService.update_entity(LaunchRequest, UUID_FIELD, getattr(req_row, UUID_FIELD), {"status": "failed", "detail": {"error": str(exc)}})
            try:
                platform_clients.update_scene_run(run_uuid, status="failed", notes=str(exc)[:500])
            except Exception:  # noqa: BLE001
                pass
            return error_response("launch failed", str(exc), 502)
        logger.info("run %s started (speed %.2fx, sim_dt %d)", run_uuid, speed_x, sim_dt_ms)
        return success_response({"scene_run_uuid": run_uuid, "speed_x": speed_x, "sim_dt_ms": sim_dt_ms, "ue": ue.get("data"), "instances": {r: {k: v for k, v in i.items() if k != "run_instance_uuid"} for r, i in instances.items()}}, "started", 201)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def stop(request):
        """body {scene_run_uuid}"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        run_uuid = str(payload.get("scene_run_uuid") or "")
        if not run_uuid:
            return error_response("Validation failed", {"scene_run_uuid": "required"}, 400)
        now = TimestampService.get_current_timestamp()
        req_row = SqlDbBusinessService.create_entity(LaunchRequest, {
            UUID_FIELD: UUIDService.generate_uuid("launch_request"), "launch_request_created_at": now, "launch_request_updated_at": now,
            "f_scene_run_uuid": run_uuid, "action": "stop", "status": "accepted"})
        try:
            ue_host = container_spawner.names_for(run_uuid)["ue"] if settings.PER_RUN_ENABLED else None
            try:
                ue = platform_clients.ue_stop(host=ue_host)
            except Exception as exc:  # noqa: BLE001
                ue = {"success": False, "message": f"ue_stop: {exc}"}   # 容器可能已死;照樣往下清
            archive_stats = cu_archiver.stop_archiver(run_uuid)
            containers = None
            if settings.PER_RUN_ENABLED:
                health_monitor.stop_monitor(run_uuid)
                containers = container_spawner.teardown(run_uuid)
                for inst in platform_clients.list_run_instances(run_uuid):
                    platform_clients.update_run_instance(inst["run_instance_uuid"], status="stopped")
            platform_clients.update_scene_run(run_uuid, status="stopped", stopped_at=now.isoformat())
            SqlDbBusinessService.update_entity(LaunchRequest, UUID_FIELD, getattr(req_row, UUID_FIELD),
                                               {"status": "stopped", "detail": ue, "launch_request_updated_at": TimestampService.get_current_timestamp()})
        except Exception as exc:  # noqa: BLE001
            logger.exception("launch stop failed run=%s", run_uuid)
            return error_response("stop failed", str(exc), 502)
        return success_response({"scene_run_uuid": run_uuid, "ue": ue.get("data"), "archive": archive_stats, "containers": containers}, "stopped", 200)
