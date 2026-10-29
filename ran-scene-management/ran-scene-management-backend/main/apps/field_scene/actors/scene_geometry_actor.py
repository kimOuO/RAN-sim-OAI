"""場景幾何(畫布顯示用):列出網格、回傳網格檔。全 POST(backend_rule §7-2)。"""
from __future__ import annotations

import json
import io

from django.http import FileResponse
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.field_scene.models.building import Building
from main.apps.field_scene.models.scene import Scene
from main.apps.field_scene.models.material import Material
from main.apps.field_scene.services.optional.scene_geometry.mitsuba_shapes import list_shapes, scene_xml_paths
from main.utils.response import error_response, success_response


def _shapes(scene_uuid: str) -> list[dict] | None:
    scene = Scene.objects.filter(scene_uuid=scene_uuid).first()
    if scene is None:
        return None
    out = []
    for xi, xml in enumerate(scene_xml_paths(scene.geometry_source, list(Building.objects.filter(scene=scene)))):
        for s in list_shapes(xml):
            out.append({**s, '_local_id': s['shape_id'], "shape_id": f"{xi}-{s['shape_id']}"})
    return out


class SceneGeometryReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def meshes(request):
        """body = {scene_uuid} → [{shape_id, name, format, material, color, bytes, too_large, transform}]"""
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        shapes = _shapes(str(payload.get("scene_uuid") or ""))
        if shapes is None:
            return error_response("Not found", payload.get("scene_uuid"), 404)
        return success_response([{k: v for k, v in s.items() if not k.startswith("_")} for s in shapes], "ok", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def mesh_file(request):
        """body = {scene_uuid, shape_id} → 網格檔原始位元組(只限該場景引用的檔案)"""
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        shapes = _shapes(str(payload.get("scene_uuid") or "")) or []
        s = next((x for x in shapes if x["shape_id"] == payload.get("shape_id")), None)
        if s is None or s["too_large"]:
            return error_response("Not found", payload.get("shape_id"), 404)
        if '_vertex_range' in s:
            from main.apps.field_scene.services.optional.scene_geometry.osm_mesh_parts import part_bytes
            stream = io.BytesIO(part_bytes(s['_path'], s['_vertex_range']))
        else:
            stream = open(s['_path'], 'rb')
        resp = FileResponse(stream, content_type="application/octet-stream")
        resp["Cache-Control"] = "private, max-age=3600"
        return resp


    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def bounds(request):
        """body = {scene_uuid} → {x_range, z_range}(含掃描模型的實際邊界)。

        2026-09-20:編輯器的「UE 隨機產生」範圍與覆蓋熱圖範圍原本都只看建築盒 /
        gNB / UE 路徑,掃描模型的尺寸沒納入 —— 只有兩個 gNB 的場景就只會在一小塊
        長方形裡生成。這支把 physics 回報的 Mitsuba bbox 一併算進去。
        """
        from main.apps.field_scene.services.optional.scene_geometry.coverage import geometry_bounds
        from main.apps.field_scene.services.optional.scenario_import.scenario_v1 import export_scenario
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        uid = str(payload.get("scene_uuid") or "")
        if not Scene.objects.filter(scene_uuid=uid).exists():
            return error_response("Not found", uid, 404)
        raw = export_scenario(uid)
        gb = geometry_bounds(raw)
        if gb is None:
            return success_response({"x_range": None, "z_range": None}, "無幾何邊界(沒有掃描模型或 physics 不通)", 200)
        return success_response({"x_range": gb[0], "z_range": gb[1]}, "ok", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def height_map(request):
        """body = {scene_uuid, step_m?=4} → 每格表面高度(給 UE 隨機產生避開建築)。
        範圍取場景幾何邊界;掃描模型沒有建築盒資料,只能靠射線取高度。"""
        import json as _json
        import urllib.request as _ur

        from main.apps.field_scene.services.optional.scene_geometry.coverage import (
            PHYSICS_URL, geometry_bounds,
        )
        from main.apps.field_scene.services.optional.scenario_import.scenario_v1 import export_scenario
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        uid = str(payload.get("scene_uuid") or "")
        if not Scene.objects.filter(scene_uuid=uid).exists():
            return error_response("Not found", uid, 404)
        raw = export_scenario(uid)
        gb = geometry_bounds(raw)
        if gb is None:
            return error_response("這個場景沒有可取邊界的幾何(需要掃描模型 / OSM)", None, 400)
        body = {"geometry_source": raw.get("geometry_source"), "x_range": gb[0], "z_range": gb[1],
                "step_m": float(payload.get("step_m", 4.0))}
        req = _ur.Request(f"{PHYSICS_URL}/api/v0.1/Physics/RanSignal/CoverageRunner/height_map",
                          data=_json.dumps(body).encode(), headers={"content-type": "application/json"})
        try:
            with _ur.urlopen(req, timeout=300) as r:
                return success_response(_json.load(r)["data"], "ok", 200)
        except Exception as exc:  # noqa: BLE001
            return error_response("height_map failed", str(exc), 502)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def coverage(request):
        """body = {scene_uuid, sample_height_m?=1.5, step_m?, margin_m?=5, grid?, max_depth?=3} → {grid, summary{best_rsrp_dbm, sinr_db, best_cell, cell_names}}
        (physics 另建暫時 engine 算,不影響 live run;格數上限 40000)"""
        from main.apps.field_scene.services.optional.scene_geometry.coverage import compute
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        if not Scene.objects.filter(scene_uuid=payload.get("scene_uuid")).exists():
            return error_response("Not found", payload.get("scene_uuid"), 404)
        try:
            data = compute(payload["scene_uuid"], grid=payload.get("grid"), height=float(payload.get("sample_height_m", 1.5)),
                           step=(float(payload["step_m"]) if payload.get("step_m") else None), max_depth=int(payload.get("max_depth", 3)),
                           margin=float(payload.get("margin_m", 5.0)))
        except ValueError as exc:
            return error_response(str(exc), None, 400)
        except Exception as exc:  # noqa: BLE001
            return error_response("coverage failed", str(exc), 502)
        return success_response(data, "ok", 200)

class SceneGeometryController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(['POST'])
    @transaction.atomic
    def set_material(request):
        try:
            payload = json.loads(request.body or b'{}')
            uid, shape_id, material_uuid = (payload.get(k) for k in ('scene_uuid', 'shape_id', 'material_uuid'))
        except (ValueError, AttributeError):
            return error_response('Invalid JSON', None, 400)
        scene = Scene.objects.select_for_update().filter(scene_uuid=uid).first()
        if scene is None:
            return error_response('找不到場景', uid, 404)
        # Changing an executing scene would mix simulation inputs and observations.
        if scene.runs.filter(status__in=['running', 'precomputing']).exists():
            return error_response('請先停止模擬或預算，再修改建築材質', None, 409)
        material = Material.objects.filter(material_uuid=material_uuid).first()
        if material is None:
            return error_response('找不到材質', material_uuid, 400)
        selected = next((s for s in _shapes(uid) or [] if s['shape_id'] == shape_id), None)
        if selected is None:
            return error_response('找不到選取的建築／網格', shape_id, 404)
        geo = scene.geometry_source if isinstance(scene.geometry_source, dict) else {}
        from main.apps.field_scene.services.optional.scene_geometry.mitsuba_shapes import resolve
        if geo.get('type') != 'mitsuba_xml_path' or resolve(str(geo.get('path') or '')) != resolve(selected['_xml_path']):
            return error_response('請先將這個模型設為場景幾何來源，再編輯材質', None, 400)
        try:
            from main.apps.field_scene.services.optional.scene_geometry.mesh_material import set_material
            path = set_material(selected['_xml_path'], selected['_local_id'], material.itu_id, uid)
        except (ValueError, OSError) as exc:
            return error_response('材質儲存失敗', str(exc), 400)
        from main.apps.field_scene.services.common.timestamp_service import TimestampService
        scene.geometry_source = {**geo, 'path': path}
        scene.scene_updated_at = TimestampService.get_current_timestamp()
        scene.save(update_fields=['geometry_source', 'scene_updated_at'])
        scene.runs.update(cache_path='')
        return success_response({'shape_id': shape_id, 'material': material.itu_id,
                                 'geometry_source': scene.geometry_source, 'cache_invalidated': True}, '建築材質已儲存，快取模式需重新預算', 200)
