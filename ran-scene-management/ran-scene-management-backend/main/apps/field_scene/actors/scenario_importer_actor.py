
"""ScenarioImporter — 劇本 v1 JSON 匯入 / 匯出(custom action,全 POST)。"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.field_scene.services.optional.scenario_import.scenario_v1 import export_scenario, import_scenario
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class ScenarioImporter:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def import_v1(request):
        """body = 劇本 raw_json 本體,或 {"raw_json": {...}, "precompute_status": "...", "cache_path": "..."}。"""
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        raw = payload.get("raw_json") if isinstance(payload.get("raw_json"), dict) else payload
        if not raw.get("scenario_id"):
            return error_response("Validation failed", {"scenario_id": "required"}, 400)
        try:
            result = import_scenario(raw, precompute_status=str(payload.get("precompute_status") or "pending"),
                                     cache_path=str(payload.get("cache_path") or ""))
        except Exception as exc:  # noqa: BLE001
            logger.exception("scenario import failed: %s", raw.get("scenario_id"))
            return error_response("Import failed", str(exc), 400)
        logger.info("scenario imported %s → %s", raw.get("scenario_id"), result["scene_uuid"])
        return success_response(result, "imported", 201)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def export_v1(request):
        """body = {"scene_uuid": ..., "scene_run_uuid"?: ...} → 劇本 v1 raw_json。"""
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        if not payload.get("scene_uuid"):
            return error_response("Validation failed", {"scene_uuid": "required"}, 400)
        try:
            raw = export_scenario(payload["scene_uuid"], payload.get("scene_run_uuid"))
        except Exception as exc:  # noqa: BLE001
            return error_response("Export failed", str(exc), 404)
        return success_response(raw, "ok", 200)
