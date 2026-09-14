"""Precompute actors(2026-09-14)— 場景預算(cached 模式的 channel cache)。
PrecomputeController.start / stop、PrecomputeReader.read。全 POST(backend_rule §7-2)。
狀態機:registry scene_run.status draft|pending|failed → precomputing → ready(容器 exit 0 且 npz 存在)| failed。"""
from __future__ import annotations

import json
import os
import threading
import time

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.run_lifecycle.services.optional import container_spawner, platform_clients
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)
CACHE_DIR_IN_CONTAINER = "/app/data/channel_cache"


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


def _watch(scene_run_uuid: str, scenario_id: str) -> None:
    """等 precompute 容器結束,把結果寫回 registry。"""
    while True:
        st = container_spawner.precompute_status(scene_run_uuid)
        if st.get("state") in ("exited", "dead", "absent"):
            ok = st.get("exit_code") == 0 and st.get("done")
            cache_path = f"{CACHE_DIR_IN_CONTAINER}/{scenario_id}.npz"
            try:
                platform_clients.update_scene_run(scene_run_uuid, status="ready" if ok else "failed", cache_path=cache_path if ok else "",
                                                  notes=("precompute ok" if ok else f"precompute failed exit={st.get('exit_code')}: {' | '.join(st.get('last_lines') or [])[:400]}"))
            except Exception:  # noqa: BLE001
                logger.exception("precompute result write-back failed %s", scene_run_uuid)
            logger.info("precompute %s finished ok=%s", scene_run_uuid, ok)
            return
        time.sleep(15)


class PrecomputeController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def start(request):
        """body {scene_run_uuid, segment_ticks?}"""
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
        t = tree["data"]; run = t.get("run") or {}; scene = t.get("scene") or {}
        # 舊劇本用 legacy id 當 cache 檔名(相容既有 npz);手動建的場景用 scene_uuid(registry shim 兩種都認)
        scenario_id = str(scene.get("legacy_scenario_id") or scene.get("scene_uuid") or "")
        if not scenario_id:
            return error_response("scene has no id", run_uuid, 400)
        if run.get("status") == "running":
            return error_response("run 執行中,先停再預算", run_uuid, 409)
        if run.get("mode") != "cached":
            return error_response("只有 cached 模式需要預算", run.get("mode"), 400)
        try:
            info = container_spawner.spawn_precompute(run_uuid, scenario_id, int(payload.get("segment_ticks") or 10000))
            platform_clients.update_scene_run(run_uuid, status="precomputing", notes=f"precompute started {scenario_id}")
            threading.Thread(target=_watch, args=(run_uuid, scenario_id), name=f"precompute-watch-{run_uuid[-8:]}", daemon=True).start()
        except Exception as exc:  # noqa: BLE001
            logger.exception("precompute start failed %s", run_uuid)
            return error_response("precompute start failed", str(exc), 502)
        return success_response({"scene_run_uuid": run_uuid, **info}, "precompute started", 201)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def stop(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        run_uuid = str(payload.get("scene_run_uuid") or "")
        if not run_uuid:
            return error_response("Validation failed", {"scene_run_uuid": "required"}, 400)
        res = container_spawner.stop_precompute(run_uuid)
        try:
            platform_clients.update_scene_run(run_uuid, status="pending", notes="precompute stopped")
        except Exception:  # noqa: BLE001
            pass
        return success_response({"scene_run_uuid": run_uuid, "container": res}, "precompute stopped", 200)


class PrecomputeReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        """body {scene_run_uuid} → 容器狀態 + 進度(tick / % / rate / ETA)"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        run_uuid = str(payload.get("scene_run_uuid") or "")
        if not run_uuid:
            return error_response("Validation failed", {"scene_run_uuid": "required"}, 400)
        return success_response({"scene_run_uuid": run_uuid, **container_spawner.precompute_status(run_uuid)}, "ok", 200)
