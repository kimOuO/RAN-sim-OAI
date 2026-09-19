"""GET /status —— 給 RIC 端在更新元件前查「現在有沒有 run 在跑」的唯讀端點。

2026-09-19 RIC 端請求:他們會在每次更新 RIC 元件前自動查,`running` 非空就不動。
刻意不放在 /api/v0.1/... 底下,也不需要任何參數 —— 這是給外部維運腳本用的,越簡單越好。
"""
from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.run_lifecycle.services.optional import platform_clients
from main.utils.logger import get_logger

logger = get_logger(__name__)


def _purpose_of(run: dict) -> str:
    knobs = run.get("knobs") or {}
    if isinstance(knobs, dict):
        return str(knobs.get("ric_purpose") or "")
    if isinstance(knobs, list):   # 舊格式:[{key, value}, ...]
        return str(next((k.get("value") for k in knobs
                         if isinstance(k, dict) and k.get("key") == "ric_purpose"), "") or "")
    return ""


@csrf_exempt
@require_http_methods(["GET"])
def status(request):
    try:
        runs = platform_clients.list_runs_by_status("running")
    except Exception as exc:   # noqa: BLE001 — registry 不通時不能假裝「沒有 run」
        logger.warning("status: registry 查詢失敗 %s", exc)
        return JsonResponse({"error": "registry unreachable", "detail": str(exc)[:200]}, status=503)
    out = []
    for r in runs:
        if not isinstance(r, dict):
            continue
        uid = r.get("scene_run_uuid")
        # scene_run 本身沒有場景名,也沒有 knobs —— 兩者都在 read_full_tree(同時在跑的 run 很少,逐一查可接受)
        name, purpose = "", ""
        try:
            t = platform_clients.read_full_tree(uid).get("data") or {}
            sc = t.get("scene") or {}
            name = str(sc.get("name") or sc.get("legacy_scenario_id") or "")
            purpose = _purpose_of(t.get("run") or {})
        except Exception as exc:   # noqa: BLE001 — 查不到名字不該讓整個端點失敗
            logger.warning("status: scene_tree %s 失敗 %s", uid, exc)
        out.append({"scene_run_uuid": uid, "scene_name": name,
                    "started_at": r.get("started_at"), "purpose": purpose})
    return JsonResponse({"running": out})
