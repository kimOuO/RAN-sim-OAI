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

from main.apps.e2_adapter.services.optional.event_log.ring import get_control_ring
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)

_RAN_FUNC_NAME = {2: "KPM", 3: "RC", 4: "CCC", 5: "FULLKPM", 6: "ANR", 7: "FULLKPM2", 8: "ANR2"}


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

        # 專用 ring,裡面只有控制事件 —— 不會被 indication 擠掉(見 ring.py 的說明)
        entries = get_control_ring().read(since_seq=0, limit=500)
        rows: dict[tuple, dict] = {}
        order: list[tuple] = []

        for e in entries:
            kind = e.get("kind")
            if kind not in ("control_req_recv", "control_ack_sent", "control_failure"):
                continue
            # 2026-09-23:一則請求一列。以前以 (ran_func, inst_id, sim_action) 為鍵,
            # RIC 的 xApp 對多筆命令重用同一個 instId → 6 筆 anr-add 被併成 1 列、
            # 3-1 / 2-6 併進更早的列 —— 歸檔端只認新 seq,併掉的全部消失在 I-7。
            # 改成:control_req_recv 一律開新列(鍵 = 自己的 seq);ack / failure 附到
            # 同 (ran_func, inst_id) **最近一筆尚未 ack 的列**,找不到才自成一列。
            if kind == "control_req_recv" or e.get("inst_id") is None:
                key = ("_seq", e.get("seq"), kind if kind != "control_req_recv" else "req")
            else:
                key = next((k for k in reversed(order)
                            if k[0] == "_seq" and rows[k].get("ranFunc") == e.get("ran_func")
                            and rows[k].get("instId") == e.get("inst_id") and not rows[k]["acked"]
                            and not rows[k]["failure"]), ("_seq", e.get("seq"), kind))
            if key not in rows:
                rows[key] = {
                    "seq": e["seq"], "ts_ms": e["ts_ms"],
                    "ranFunc": e.get("ran_func"),
                    "ranFuncName": _RAN_FUNC_NAME.get(e.get("ran_func"), "?"),
                    "instId": e.get("inst_id"),
                    # RIC 對帳鍵(多 gNB C14):E2AP RICrequestID 的 requestor 與 RICcallProcessID 標籤。
                    # 以前 ring 有記、這裡沒輸出 → 歸檔 / I-7 的 ric_label、ric_requestor_id 一直是空的。
                    "requestorId": e.get("requestor_id"),
                    "ricLabel": e.get("ric_label"),
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
