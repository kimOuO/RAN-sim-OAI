"""TelemetryExportReader — 供 run-orchestrator 封存用的游標式匯出(2026-09-13 P2-3)。

body: {"since": {"measurement": id, "cell": id, "handover": id, "rlf": id}, "limit": 500} 或 {"max_only": true}
回:{measurement: [...], cell: [...], handover: [...], rlf: [...], cursor: {同 since 形狀,= 各表本批最大 id}}
只讀、不改狀態;四張表本來就每個 PM 視窗由 F1 上報落地,與 RIC 無關。
"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.models.cell_measurement_log import CellMeasurementLog
from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.models.measurement_log import MeasurementLog
from main.apps.cu_cp.models.rlf_event import RlfEvent
from main.utils.response import error_response, success_response

_TABLES = {
    "measurement": (MeasurementLog, ("id", "ue_id", "serving_cell", "rsrp_dbm", "sinr_db", "throughput_dl_mbps", "throughput_ul_mbps",
                                     "mcs_dl", "rb_width_dl", "mimo_rank", "pdcp_sdu_volume_dl", "pdcp_sdu_volume_ul",
                                     "rlc_sdu_delay_dl_ms", "qos_5qi", "neighbor_cells_json", "recorded_at",
                                     "mcs_ul", "rb_width_ul", "ul_sinr_db", "sinr_layers_json")),
    "cell": (CellMeasurementLog, ("id", "cell_id", "prb_pct_dl", "prb_pct_ul", "tick_count", "window_seconds", "recorded_at")),
    "handover": (HandoverEvent, ("id", "ue_id", "source_cell", "target_cell", "trigger", "status", "started_at", "completed_at",
                                 "failure_cause", "mro_class")),
    "rlf": (RlfEvent, ("id", "ue_id", "source_cell", "source_pci", "sinr_at_rlf", "t310_ms", "reason", "reestab_cell", "reestab_pci")),
}


class TelemetryExportReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        since = body.get("since") or {}
        limit = max(1, min(int(body.get("limit", 500)), 5000))
        out: dict = {"cursor": {}}
        if body.get("max_only"):   # 只回各表目前最大 id(archiver 啟動時定游標,免翻頁)
            from django.db.models import Max
            out["cursor"] = {k: (model.objects.aggregate(m=Max("id"))["m"] or 0) for k, (model, _) in _TABLES.items()}
            return success_response(out, "ok", 200)
        for key, (model, fields) in _TABLES.items():
            last = int(since.get(key, 0) or 0)
            rows = list(model.objects.filter(id__gt=last).order_by("id").values(*fields)[:limit])
            for r in rows:
                for f in ("recorded_at", "started_at", "completed_at"):
                    if r.get(f) is not None:
                        r[f] = r[f].isoformat()
            out[key] = rows
            out["cursor"][key] = rows[-1]["id"] if rows else last
        return success_response(out, "ok", 200)
