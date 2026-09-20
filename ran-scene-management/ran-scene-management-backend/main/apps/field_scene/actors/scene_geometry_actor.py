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
