"""OSM:geocode(地名→bbox)/ generate(bbox→Mitsuba)/ read / delete / attach_to_scene。
流程自 Omniverse map_actor.geocode / generate 複製,拿掉 USD 與 Kit 推送。"""
from __future__ import annotations

import json
import os

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.render_osm_footprint.models.osm_map_asset import OsmMapAsset
from main.apps.render_osm_footprint.serializers.osm_map_asset_serializers import OsmMapAssetReadSerializer
from main.apps.render_osm_footprint.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.render_osm_footprint.services.common.timestamp_service import TimestampService
from main.apps.render_osm_footprint.services.common.uuid_service import UUIDService
from main.apps.render_osm_footprint.services.optional.nominatim_client import geocode as nominatim_geocode
from main.apps.render_osm_footprint.services.optional.osm_to_mitsuba import build_mitsuba_from_edit, convert_osm_to_mitsuba, preview_buildings
from main.apps.render_osm_footprint.services.optional.overpass_client import fetch_osm
from main.apps.render_scan_mesh.services.optional import registry_client
from main.apps.render_scan_mesh.services.optional.asset_paths import asset_base
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)
UUID_FIELD = "osm_map_asset_uuid"


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


class OsmFootprintImporter:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def geocode(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        q = (payload.get("query") or "").strip()
        if not q:
            return error_response("Missing query", {}, 400)
        try:
            results = nominatim_geocode(q, limit=int(payload.get("limit") or 5))
        except Exception as exc:  # noqa: BLE001
            return error_response("地標搜尋失敗", str(exc), 502)
        return success_response({"results": results, "count": len(results)}, "ok", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def generate(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        name = (payload.get("name") or "").strip()
        if not name:
            return error_response("Missing name", {}, 400)
        try:
            min_lon, min_lat, max_lon, max_lat = (float(payload[k]) for k in ("min_lon", "min_lat", "max_lon", "max_lat"))
        except (KeyError, TypeError, ValueError):
            return error_response("需要 min_lon / min_lat / max_lon / max_lat(數字)", {}, 400)
        if min_lon >= max_lon or min_lat >= max_lat:
            return error_response("座標範圍無效(min 必須 < max)", {}, 400)
        if (max_lat - min_lat) > 0.03 or (max_lon - min_lon) > 0.03:
            return error_response("範圍過大(建議 < 0.03 度 ≈ 3km)", {}, 400)
        now = TimestampService.now()
        base = asset_base("osm", name)
        asset, _ = OsmMapAsset.objects.update_or_create(name=name, defaults={
            "label": str(payload.get("label") or name), "min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat,
            "status": "pending", "error": "", "osm_map_asset_updated_at": now,
            **({"osm_map_asset_uuid": UUIDService.generate_uuid("osm_map_asset"), "osm_map_asset_created_at": now} if not OsmMapAsset.objects.filter(name=name).exists() else {})})
        try:
            osm_xml = fetch_osm(min_lat, min_lon, max_lat, max_lon)
            stats = convert_osm_to_mitsuba(osm_xml, (min_lat, min_lon, max_lat, max_lon), base + ".mitsuba.xml")
            asset.mitsuba_xml = stats["mitsuba_path"]
            asset.footprints_json = stats["footprints_path"]
            asset.building_count = stats["building_count"]
            asset.height_max_m = stats["height_max_m"]
            asset.extent_ew_m = stats["extent_ew_m"]
            asset.extent_ns_m = stats["extent_ns_m"]
            asset.origin_lat = stats["origin_lat"]
            asset.origin_lon = stats["origin_lon"]
            asset.status = "ready"
            asset.error = ""
            asset.osm_map_asset_updated_at = TimestampService.now()
            asset.save()
            return success_response(OsmMapAssetReadSerializer(asset).data, f"地圖 {name} 產生完成({stats['building_count']} 棟)", 201)
        except Exception as exc:  # noqa: BLE001
            logger.exception("MapGen %s failed", name)
            asset.status = "failed"
            asset.error = str(exc)
            asset.save(update_fields=["status", "error"])
            return error_response("地圖產生失敗", str(exc), 500)


MAX_AREA_M2 = 1_000_000   # 1 km²:Overpass 與光追成本的上限


def _polygon(payload: dict) -> list[list[float]]:
    poly = payload.get("polygon") or []
    if len(poly) < 3 or not all(isinstance(p, (list, tuple)) and len(p) == 2 for p in poly):
        raise ValueError("polygon 需要至少 3 個 [lat, lon]")
    return [[float(p[0]), float(p[1])] for p in poly]


class OsmMapEditor:
    """地圖編輯流程:多邊形 → preview(逐棟建築,可改材質/高度)→ build_scene(產生 Mitsuba 並設為場景幾何)。"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def preview(request):
        """body {polygon:[[lat,lon],...]} → {buildings:[{id,name,outer,inner,base_m,height_m,height_known,material}], area_m2}"""
        try:
            payload = _body(request)
            poly = _polygon(payload)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            return error_response("Validation failed", str(exc), 400)
        lats, lons = [p[0] for p in poly], [p[1] for p in poly]
        try:
            osm_xml = fetch_osm(min(lats), min(lons), max(lats), max(lons))
            res = preview_buildings(osm_xml, poly)
        except Exception as exc:  # noqa: BLE001
            logger.exception("OSM preview failed")
            return error_response("抓取 OSM 失敗", str(exc), 502)
        if res["area_m2"] > MAX_AREA_M2:
            return error_response(f"範圍 {res['area_m2'] / 1e6:.2f} km² 超過上限 1 km²", {}, 400)
        return success_response(res, f"{len(res['buildings'])} 棟", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def build_scene(request):
        """body {scene_uuid, name, polygon, buildings:[{outer,inner?,base_m,height_m,material}]}
        → 產生 Mitsuba,並把場景的 geometry_source 設成它(physics 與畫布同一路徑)。"""
        try:
            payload = _body(request)
            poly = _polygon(payload)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            return error_response("Validation failed", str(exc), 400)
        scene_uuid, name = payload.get("scene_uuid"), (payload.get("name") or "").strip()
        buildings = payload.get("buildings") or []
        if not scene_uuid or not name or not buildings:
            return error_response("需要 scene_uuid、name、buildings", {}, 400)
        try:
            itu_of = registry_client.material_itu_map()
            stats = build_mitsuba_from_edit(poly, buildings, itu_of, asset_base("osm", name) + ".mitsuba.xml")
        except ValueError as exc:
            return error_response("產生失敗", str(exc), 400)
        except Exception as exc:  # noqa: BLE001
            logger.exception("OSM build_scene failed")
            return error_response("產生失敗", str(exc), 500)
        lats, lons = [p[0] for p in poly], [p[1] for p in poly]
        try:
            registry_client.update_scene(
                scene_uuid,
                geometry_source={"type": "mitsuba_xml_path", "path": stats["mitsuba_path"], "origin": "osm", "polygon": poly},
                geometry_scene_id=name, origin_lat=stats["origin_lat"], origin_lon=stats["origin_lon"],
                bounds={"min_lat": min(lats), "min_lon": min(lons), "max_lat": max(lats), "max_lon": max(lons)})
        except Exception as exc:  # noqa: BLE001
            return error_response("場景更新失敗", str(exc), 502)
        return success_response(stats, f"場景幾何已產生({stats['building_count']} 棟)", 201)


class OsmMapAssetReader:
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
            a = SqlDbBusinessService.get_or_none(OsmMapAsset, key, val)
            if a is None:
                return error_response("Not found", val, 404)
            return success_response(OsmMapAssetReadSerializer(a).data, "ok", 200)
        return success_response(OsmMapAssetReadSerializer(SqlDbBusinessService.list_entities(OsmMapAsset), many=True).data, "ok", 200)


class OsmMapAssetController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def delete(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        a = SqlDbBusinessService.get_or_none(OsmMapAsset, UUID_FIELD, payload.get(UUID_FIELD, ""))
        if a is None:
            return error_response("Not found", payload.get(UUID_FIELD), 404)
        for p in (a.mitsuba_xml, a.footprints_json):
            if p and os.path.exists(p):
                os.remove(p)
        n = SqlDbBusinessService.delete_entity(OsmMapAsset, UUID_FIELD, a.osm_map_asset_uuid)
        return success_response({"deleted": n}, "deleted", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def attach_to_scene(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        a = SqlDbBusinessService.get_or_none(OsmMapAsset, UUID_FIELD, payload.get(UUID_FIELD, ""))
        if a is None or a.status != "ready":
            return error_response("Not found or not ready", payload.get(UUID_FIELD), 404)
        if not payload.get("scene_uuid"):
            return error_response("Validation failed", {"scene_uuid": "required"}, 400)
        try:
            r = registry_client.create_building(scene_uuid=payload["scene_uuid"], name=a.name, source="osm",
                                                geometry_ref=a.mitsuba_xml, position=payload.get("position"))
        except Exception as exc:  # noqa: BLE001
            return error_response("Registry call failed", str(exc), 502)
        return success_response(r.get("data"), "attached", 201)
