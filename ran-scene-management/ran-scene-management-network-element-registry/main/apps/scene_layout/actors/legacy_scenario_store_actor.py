"""LegacyScenarioStore — 與舊劇本倉庫(Omniverse / Physics scenario_store)同路徑同形狀的相容端點。

★ 過渡用(P1–P2):讓 RANsim-UE 的 scenario_loader 只改 SCENARIO_STORE_URL 就能吃 registry 的場景。
  P2 模擬端直接讀 read_full_tree 後刪除。URL 故意不照 backend_rule §7-1(要對齊舊路徑)。
"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.scene_layout.models.scene import Scene
from main.apps.scene_layout.services.optional.scenario_import.scenario_v1 import export_scenario
from main.apps.simulation_run.models.scene_run import SceneRun
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


def _record(scene: Scene, run: SceneRun | None, with_raw: bool) -> dict:
    raw = export_scenario(scene.scene_uuid, run.scene_run_uuid if run else None)
    ready = bool(run and run.mode == "cached")
    rec = {
        "scenario_id": raw["scenario_id"], "scene_id": raw["scene_id"],
        "duration_sec": raw["duration_sec"], "tick_ms": raw["tick_ms"], "ue_count": len(raw.get("ues") or []),
        "precompute_status": "ready" if ready else "pending", "precompute_progress": 1.0 if ready else 0.0,
        "precompute_error": "", "cache_path": (run.cache_path if run else "") or "", "cache_size_bytes": 0,
        "created_at": scene.scene_created_at.isoformat(),
        "registry": {"scene_uuid": scene.scene_uuid, "scene_run_uuid": run.scene_run_uuid if run else None},
    }
    if with_raw:
        rec["raw_json"] = raw
    return rec


def _latest_scene(scenario_id: str) -> Scene | None:
    return (Scene.objects.filter(legacy_scenario_id=scenario_id).order_by("-id").first()
            or Scene.objects.filter(name=scenario_id).order_by("-id").first())


class LegacyScenarioStore:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        sid = payload.get("scenario_id")
        if not sid:
            return error_response("Validation failed", {"scenario_id": "required"}, 400)
        scene = _latest_scene(str(sid))
        if scene is None:
            return error_response("Not found", sid, 404)
        run = SceneRun.objects.filter(scene=scene).order_by("id").first()
        return success_response(_record(scene, run, with_raw=True), "ok", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def list(request):
        rows = []
        seen: set[str] = set()
        for scene in Scene.objects.exclude(legacy_scenario_id="").order_by("-id"):
            if scene.legacy_scenario_id in seen:
                continue
            seen.add(scene.legacy_scenario_id)
            run = SceneRun.objects.filter(scene=scene).order_by("id").first()
            rows.append(_record(scene, run, with_raw=False))
        return success_response(rows, "ok", 200)
