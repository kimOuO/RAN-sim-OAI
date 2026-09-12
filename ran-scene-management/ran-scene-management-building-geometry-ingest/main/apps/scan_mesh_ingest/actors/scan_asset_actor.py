"""掃描 GLB 匯入(multipart)→ 材質分類 → Mitsuba;read / delete / attach_to_scene。
流程自 Omniverse map_actor.import_glb 複製,拿掉 USD 與 Kit 推送。"""
from __future__ import annotations

import json
import os

from django.conf import settings
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.scan_mesh_ingest.models.scan_asset import ScanAsset
from main.apps.scan_mesh_ingest.serializers.scan_asset_serializers import ScanAssetReadSerializer
from main.apps.scan_mesh_ingest.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.scan_mesh_ingest.services.common.timestamp_service import TimestampService
from main.apps.scan_mesh_ingest.services.common.uuid_service import UUIDService
from main.apps.scan_mesh_ingest.services.optional import registry_client
from main.apps.scan_mesh_ingest.services.optional.asset_paths import asset_base
from main.apps.scan_mesh_ingest.services.optional.glb_to_mitsuba import build_mitsuba_from_labels
from main.apps.scan_mesh_ingest.services.optional.scan_material_classifier import classify_and_record
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)
UUID_FIELD = "scan_asset_uuid"


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


class ScanMeshImporter:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def import_glb(request):
        """multipart:file(.glb)、name、label?、recenter?(default true)、material_mode?(conservative|legacy_color)"""
        upload = request.FILES.get("file")
        if upload is None:
            return error_response("需要上傳 file(.glb)", {}, 400)
        name = (request.POST.get("name") or "").strip()
        if not name:
            return error_response("Missing name", {}, 400)
        if upload.size > settings.MAX_GLB_BYTES:
            return error_response(f"檔案過大({upload.size / 1e6:.0f} MB),上限 {settings.MAX_GLB_BYTES / 1e6:.0f} MB", {}, 413)
        recenter = str(request.POST.get("recenter", "true")).lower() not in ("false", "0", "")
        mode = str(request.POST.get("material_mode", "conservative"))
        if mode not in ("conservative", "legacy_color"):
            return error_response("material_mode 需為 conservative 或 legacy_color", {}, 400)
        now = TimestampService.now()
        base = asset_base("scan", name)
        glb_path = base + ".glb"
        asset, created = ScanAsset.objects.update_or_create(name=name, defaults={
            "label": str(request.POST.get("label") or name), "glb_path": glb_path, "status": "pending", "error": "",
            "scan_asset_updated_at": now, **({"scan_asset_uuid": UUIDService.generate_uuid("scan_asset"), "scan_asset_created_at": now} if not ScanAsset.objects.filter(name=name).exists() else {})})
        try:
            blob = upload.read()
            with open(glb_path, "wb") as fh:
                fh.write(blob)
            radio = classify_and_record(blob, base, mode=mode)
            mitsuba = build_mitsuba_from_labels(radio["npz_path"], base + ".mitsuba.xml", recenter=recenter, ground_align=recenter)
            asset.materials_npz = radio["npz_path"]
            asset.materials_json = radio["json_path"]
            asset.mitsuba_xml = base + ".mitsuba.xml"
            asset.import_stats = mitsuba
            asset.radio_materials = radio.get("materials")
            asset.status = "ready"
            asset.error = ""
            asset.scan_asset_updated_at = TimestampService.now()
            asset.save()
            logger.info("ImportGLB %s: ready → %s", name, asset.mitsuba_xml)
            return success_response(ScanAssetReadSerializer(asset).data, "imported", 201)
        except Exception as exc:  # noqa: BLE001
            logger.exception("ImportGLB %s failed", name)
            asset.status = "failed"
            asset.error = str(exc)
            asset.save(update_fields=["status", "error"])
            return error_response("Import failed", str(exc), 500)


class ScanAssetReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        if UUID_FIELD in payload or "name" in payload:
            key, val = (UUID_FIELD, payload[UUID_FIELD]) if UUID_FIELD in payload else ("name", payload["name"])
            a = SqlDbBusinessService.get_or_none(ScanAsset, key, val)
            if a is None:
                return error_response("Not found", val, 404)
            return success_response(ScanAssetReadSerializer(a).data, "ok", 200)
        return success_response(ScanAssetReadSerializer(SqlDbBusinessService.list_entities(ScanAsset), many=True).data, "ok", 200)


class ScanAssetController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def delete(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        a = SqlDbBusinessService.get_or_none(ScanAsset, UUID_FIELD, payload.get(UUID_FIELD, ""))
        if a is None:
            return error_response("Not found", payload.get(UUID_FIELD), 404)
        for p in (a.glb_path, a.materials_npz, a.materials_json, a.mitsuba_xml):
            if p and os.path.exists(p):
                os.remove(p)
        n = SqlDbBusinessService.delete_entity(ScanAsset, UUID_FIELD, a.scan_asset_uuid)
        return success_response({"deleted": n}, "deleted", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def attach_to_scene(request):
        """body {scan_asset_uuid, scene_uuid, position?, rotation?, scale?} → registry building 一列。"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        a = SqlDbBusinessService.get_or_none(ScanAsset, UUID_FIELD, payload.get(UUID_FIELD, ""))
        if a is None or a.status != "ready":
            return error_response("Not found or not ready", payload.get(UUID_FIELD), 404)
        if not payload.get("scene_uuid"):
            return error_response("Validation failed", {"scene_uuid": "required"}, 400)
        try:
            r = registry_client.create_building(scene_uuid=payload["scene_uuid"], name=a.name, source="glb_scan",
                                                geometry_ref=a.mitsuba_xml, materials_npz=a.materials_npz,
                                                position=payload.get("position"), rotation=payload.get("rotation"), scale=payload.get("scale"))
        except Exception as exc:  # noqa: BLE001
            return error_response("Registry call failed", str(exc), 502)
        return success_response(r.get("data"), "attached", 201)
