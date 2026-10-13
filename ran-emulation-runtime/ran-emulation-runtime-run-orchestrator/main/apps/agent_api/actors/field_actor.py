"""外部 Agent 介面 I-2 — 取得場域配置。

對方以此份配置當分析基準,並依其中的 E2 識別部署 xApp 到 RIC,所以
identity 欄位的正確性等同功能正確性(見 services/optional/field_config)。
"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.agent_api.services.optional import field_config, field_list
from main.apps.run_lifecycle.services.optional import platform_clients
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


class FieldReader:
    """Component name in URL: FieldReader"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def list(request):
        """I-1 場域清單。body {} —— 可選 `ready_only`:只列已備妥可跑的。

        只列釘了 e2_block 的場域(其餘識別會浮動,對方拿去部署 xApp 會訂不到)。
        要全部列出時帶 `all: true`。
        """
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        show_all = bool(payload.get("all"))
        ready_only = bool(payload.get("ready_only"))
        # 2026-09-22:依分類篩(corridor / anr / intent / scale / other);不給 = 全部
        want_cat = str(payload.get("category") or "").strip().lower() or None
        try:
            scenes = (platform_clients.list_scenes() or {}).get("data") or []
            runs = (platform_clients.list_scene_runs() or {}).get("data") or []
        except Exception as exc:  # noqa: BLE001
            return error_response("registry unreachable", str(exc), 502)

        run_of: dict[str, dict] = {}
        for r in runs:
            # 一個場景可能有多個 run(草稿 + 實際用的);挑有 cache_path 的那個,都沒有就挑第一個
            key = str(r.get("f_scene_uuid") or "")
            cur = run_of.get(key)
            if cur is None or (not cur.get("cache_path") and r.get("cache_path")):
                run_of[key] = r

        fields = []
        for sc in scenes:
            if not show_all and not sc.get("e2_block"):
                continue
            uuid = str(sc.get("scene_uuid") or "")
            try:
                res = platform_clients.read_scene_tree(uuid)
            except Exception:  # noqa: BLE001 — 單一場景讀不到不該讓整份清單失敗
                logger.warning("場域樹讀取失敗,略過:%s", uuid)
                continue
            if not res.get("success"):
                continue
            row = field_list.build_one(res["data"], run_of.get(uuid))
            if ready_only and not row.get("ready"):
                continue
            if want_cat and str(row.get("category") or "") != want_cat:
                continue
            fields.append(row)

        fields.sort(key=lambda f: str(f.get("name") or ""))
        return success_response({"fields": fields, "count": len(fields)}, "ok", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def config(request):
        """body {field_id}  —— field_id 是 registry 的 scene_uuid,亦接受場景名稱。"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        field_id = str(payload.get("field_id") or "").strip()
        if not field_id:
            return error_response("Validation failed", {"field_id": "required"}, 400)

        scene_uuid = field_id
        if not field_id.startswith("scene-"):
            # 也允許用名稱查。名稱目前沒有唯一性約束,撞名就明講而不是隨便挑一個。
            try:
                rows = (platform_clients.list_scenes() or {}).get("data") or []
            except Exception as exc:  # noqa: BLE001
                return error_response("registry unreachable", str(exc), 502)
            hit = [r for r in rows if r.get("name") == field_id]
            if not hit:
                return error_response("field not found", field_id, 404)
            if len(hit) > 1:
                return error_response("field name is ambiguous",
                                      {"name": field_id, "scene_uuids": [r.get("scene_uuid") for r in hit]}, 409)
            scene_uuid = str(hit[0].get("scene_uuid"))

        try:
            res = platform_clients.read_scene_tree(scene_uuid)
        except Exception as exc:  # noqa: BLE001
            return error_response("registry unreachable", str(exc), 502)
        if not res.get("success"):
            return error_response("field not found", scene_uuid, 404)

        # 幾何範圍是選配 —— 沒有 mesh 的場景抓不到,不該讓整支失敗
        bounds = None
        try:
            b = platform_clients.scene_bounds(scene_uuid)
            bounds = b.get("data") if b.get("success") else None
        except Exception:  # noqa: BLE001
            logger.info("scene_bounds 取不到(場景可能沒有 mesh):%s", scene_uuid)

        return success_response(field_config.build(res["data"], bounds), "ok", 200)
