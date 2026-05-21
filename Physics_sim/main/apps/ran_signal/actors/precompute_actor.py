"""PrecomputeActor — Phase B B.6 trigger Sionna offline precompute as background job.

POST /api/v0.1/Physics/Precompute/run    {scenario_id}
POST /api/v0.1/Physics/Precompute/status (no body) → 目前正在跑的 scenario_id 與 PID

實際算 path_gain → 寫 npz 的程式在 /app/precompute/run_precompute.py;這裡只是
HTTP wrapper 把它跑成 subprocess。Dashboard 不用 docker exec。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading

from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


logger = get_logger(__name__)


_PRECOMPUTE_SCRIPT = "/app/precompute/run_precompute.py"
_state_lock = threading.Lock()
_current: dict = {"scenario_id": "", "pid": None, "running": False}


def _run_subprocess(scenario_id: str):
    """Run precompute script as subprocess (so Sionna 計算與 Django 主程序隔離)."""
    global _current
    try:
        env = os.environ.copy()
        proc = subprocess.Popen(
            [sys.executable, _PRECOMPUTE_SCRIPT, scenario_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            bufsize=1,
            text=True,
        )
        with _state_lock:
            _current["pid"] = proc.pid
        for line in iter(proc.stdout.readline, ""):
            logger.info("[precompute %s] %s", scenario_id, line.rstrip())
        proc.wait()
        logger.info("Precompute subprocess exit code=%d", proc.returncode)
    except Exception as e:
        logger.exception("Precompute subprocess failed: %s", e)
    finally:
        with _state_lock:
            _current["running"] = False
            _current["pid"] = None


class PrecomputeActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def run(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), 400)
        scenario_id = (body.get("scenario_id") or "").strip()
        if not scenario_id:
            return error_response("scenario_id required", {}, 400)

        with _state_lock:
            if _current["running"]:
                return error_response(
                    f"Already running precompute for {_current['scenario_id']}",
                    {"running_scenario": _current["scenario_id"]},
                    409,
                )
            _current["scenario_id"] = scenario_id
            _current["running"] = True
            _current["pid"] = None

        threading.Thread(
            target=_run_subprocess, args=(scenario_id,), daemon=True,
            name=f"precompute-{scenario_id}",
        ).start()
        logger.info("Precompute job queued: scenario_id=%s", scenario_id)
        return success_response(
            {"scenario_id": scenario_id, "running": True},
            "Precompute job started",
            202,
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def status(request: HttpRequest):
        with _state_lock:
            return success_response(dict(_current), "OK")
