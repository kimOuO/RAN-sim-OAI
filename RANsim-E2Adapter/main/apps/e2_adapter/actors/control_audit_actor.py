"""下發命令稽核 —— xApp 經 E2 下到 sim 的所有 RIC Control,一個地方看完。

URL: POST /api/v0.1/E2Adapter/ControlAudit/ControlAuditReader/read
Body: { limit: int (預設 50) }

為什麼在 adapter:RC(func 3)、CCC(func 4)、ANR(func 6)三種控制**都經過這裡**,
是唯一的單一咽喉點;而且只有這一層握有 instId、ACK bytes、rtt —— CU 看不到這些。
上行的 indication 走 /e2 既有兩支端點,這支補的是下行,兩者合起來才是完整雙向視圖。

req 與 ack 依 (ran_func, inst_id) 配對成一列。配不到 ack 的(sim 還沒回、或
送 ACK 失敗)也照樣列出,acked=false —— 靜默消失才是最難查的故障。
"""
from __future__ import annotations

import json

from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.e2_adapter.services.optional.event_log.ring import get_ring
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)

_RAN_FUNC_NAME = {2: "KPM", 3: "RC", 4: "CCC", 5: "FULLKPM", 6: "ANR"}


class ControlAuditActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), status=400)
        limit = max(1, min(int(body.get("limit", 50)), 500))

        # ring 是全事件流,這裡只挑控制面三種 kind(讀多一些才夠配對出 limit 列)
        entries = get_ring().read(since_seq=0, limit=500)
        rows: dict[tuple, dict] = {}
        order: list[tuple] = []

        for e in entries:
            kind = e.get("kind")
            if kind not in ("control_req_recv", "control_ack_sent", "control_failure"):
                continue
            key = (e.get("ran_func"), e.get("inst_id"), e.get("sim_action"))
            if e.get("inst_id") is None:      # 舊格式或沒帶 instId → 用 seq 自成一列
                key = ("_seq", e.get("seq"), kind)
            if key not in rows:
                rows[key] = {
                    "seq": e["seq"], "ts_ms": e["ts_ms"],
                    "ranFunc": e.get("ran_func"),
                    "ranFuncName": _RAN_FUNC_NAME.get(e.get("ran_func"), "?"),
                    "instId": e.get("inst_id"),
                    "style": e.get("style"), "action": e.get("action"),
                    "command": e.get("sim_action", ""),
                    "params": e.get("params") or {},
                    "ueid": e.get("ueid") or {},
                    "acked": False, "result": "", "detail": "",
                    "ackBytes": None, "rttMs": None, "failure": "",
                }
                order.append(key)
            r = rows[key]
            if kind == "control_ack_sent":
                r["acked"] = True
                r["result"] = e.get("result") or ""
                r["detail"] = e.get("detail") or ""
                r["ackBytes"] = e.get("pdu_size")
                r["rttMs"] = e.get("rtt_ms")
                if e.get("outcome") and e["outcome"] != "ok":
                    r["failure"] = e["outcome"]
            elif kind == "control_failure":
                r["failure"] = e.get("reason", "failure")
                r["command"] = r["command"] or "(failed before dispatch)"

        out = [rows[k] for k in order][-limit:]
        out.reverse()   # 最新在最前面
        return success_response({"commands": out, "count": len(out)}, "ok")
