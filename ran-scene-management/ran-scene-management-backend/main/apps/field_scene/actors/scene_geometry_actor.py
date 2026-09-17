"""場景幾何(畫布顯示用):列出網格、回傳網格檔。全 POST(backend_rule §7-2)。"""
from __future__ import annotations

import json

from django.http import FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.field_scene.models.building import Building
from main.apps.field_scene.models.scene import Scene
from main.apps.field_scene.services.optional.scene_geometry.mitsuba_shapes import list_shapes, scene_xml_paths
from main.utils.response import error_response, success_response


def _shapes(scene_uuid: str) -> list[dict] | None:
    scene = Scene.objects.filter(scene_uuid=scene_uuid).first()
    if scene is None:
        return None
    out = []
    for xi, xml in enumerate(scene_xml_paths(scene.geometry_source, list(Building.objects.filter(scene=scene)))):
        for s in list_shapes(xml):
            out.append({**s, "shape_id": f"{xi}-{s['shape_id']}"})
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
        resp = FileResponse(open(s["_path"], "rb"), content_type="application/octet-stream")
        resp["Cache-Control"] = "private, max-age=3600"
        return resp

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def coverage(request):
        """body = {scene_uuid, sample_height_m?=1.5, step_m?, grid?, max_depth?=3} → {grid, summary{best_rsrp_dbm, sinr_db, best_cell, cell_names}}
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
                           step=(float(payload["step_m"]) if payload.get("step_m") else None), max_depth=int(payload.get("max_depth", 3)))
        except ValueError as exc:
            return error_response(str(exc), None, 400)
        except Exception as exc:  # noqa: BLE001
            return error_response("coverage failed", str(exc), 502)
        return success_response(data, "ok", 200)
