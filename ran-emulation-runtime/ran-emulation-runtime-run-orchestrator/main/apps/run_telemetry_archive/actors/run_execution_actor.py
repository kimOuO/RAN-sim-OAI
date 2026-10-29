"""RunExecutionReader —— 回放清單:每個 run 的每一次執行(run_seq)一列(2026-10-16)。

同一個 scene_run 可以執行很多次,歸檔以 run_seq 區分。回放頁要先讓使用者看「哪一次、何時、跑多久、
發生了什麼」再決定要不要回放,所以這裡把四張歸檔表依 (scene_run, run_seq) 彙總成一列。只讀。
"""
from __future__ import annotations

import json

from django.db.models import Count, Max, Min
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.run_telemetry_archive.models.run_control_event import RunControlEvent
from main.apps.run_telemetry_archive.models.run_handover_event import RunHandoverEvent
from main.apps.run_telemetry_archive.models.run_kpm_sample import RunKpmSample
from main.utils.response import error_response, success_response


def list_executions(run_uuid: str | None = None) -> list[dict]:
    kpm = RunKpmSample.objects.all()
    if run_uuid:
        kpm = kpm.filter(f_scene_run_uuid=run_uuid)
    rows = (kpm.values("f_scene_run_uuid", "run_seq")
            .annotate(started_ms=Min("wall_time_ms"), ended_ms=Max("wall_time_ms"),
                      sim_start=Min("scene_t_sec"), sim_end=Max("scene_t_sec"),
                      windows=Count("id"), last_id=Max("id"), ric_run=Max("ric_run")))
    key = lambda r: (r["f_scene_run_uuid"], r["run_seq"])   # noqa: E731
    ho: dict = {}
    hq = RunHandoverEvent.objects.all() if not run_uuid else RunHandoverEvent.objects.filter(f_scene_run_uuid=run_uuid)
    for r in hq.values("f_scene_run_uuid", "run_seq", "outcome").annotate(n=Count("id")):
        ho.setdefault(key(r), {})[r["outcome"]] = r["n"]
    cq = RunControlEvent.objects.all() if not run_uuid else RunControlEvent.objects.filter(f_scene_run_uuid=run_uuid)
    ctrl = {key(r): r["n"] for r in cq.values("f_scene_run_uuid", "run_seq").annotate(n=Count("id"))}
    # UE / cell 數取該次執行最後一個視窗(per_ue / per_cell 的鍵)
    last = {s.id: s for s in RunKpmSample.objects.filter(id__in=[r["last_id"] for r in rows]).only("id", "per_ue", "per_cell")}
    out = []
    for r in rows:
        k, s = key(r), last.get(r["last_id"])
        h = ho.get(k, {})
        out.append({
            "f_scene_run_uuid": r["f_scene_run_uuid"], "run_seq": r["run_seq"], "ric_run": r["ric_run"],
            "started_ms": r["started_ms"], "ended_ms": r["ended_ms"],
            "wall_sec": round(((r["ended_ms"] or 0) - (r["started_ms"] or 0)) / 1000, 1),
            "sim_start_sec": r["sim_start"], "sim_end_sec": r["sim_end"],
            "sim_sec": round((r["sim_end"] or 0) - (r["sim_start"] or 0), 1) if r["sim_end"] is not None else None,
            "windows": r["windows"],
            "ue_count": len(s.per_ue or {}) if s else 0, "cell_count": len(s.per_cell or {}) if s else 0,
            "handovers": sum(n for o, n in h.items() if o != "RLF"), "handover_succ": h.get("SUCC", 0),
            "rlf": h.get("RLF", 0), "controls": ctrl.get(k, 0),
        })
    return sorted(out, key=lambda x: x["started_ms"] or 0, reverse=True)


class RunExecutionReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        """body {f_scene_run_uuid?} → 依開始時間新到舊的執行清單。"""
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        return success_response(list_executions(payload.get("f_scene_run_uuid") or None), "ok", 200)
