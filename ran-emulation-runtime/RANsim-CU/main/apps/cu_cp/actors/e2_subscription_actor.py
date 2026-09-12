"""E2 Subscription endpoints — 對齊 OAI E2AP RIC Subscription Request/Delete + Indication poll。

對齊 OAI ref:
  - openair2/E2AP/RAN_FUNCTION/init_ran_func.c::init_ran_func_ag (subs handler 註冊)
  - openair2/E2AP/RAN_FUNCTION/O-RAN/ran_func_kpm.c::fill_kpm_ind_msg_frm_3 (indication 產生)
  - openair2/E2AP/RAN_FUNCTION/O-RAN/ran_func_kpm_subs.c (metrics 定義)

我們用 HTTP/JSON 取代 SCTP/ASN.1，但保持相同三段式語意：
  POST /E2/Subscription/create   ← OAI E2AP RIC Subscription Request
  POST /E2/Subscription/delete   ← OAI E2AP RIC Subscription Delete Request
  POST /E2/Indication/poll       ← OAI E2AP RIC Indication（polling 版，取代 SCTP push）
"""
from __future__ import annotations

import json
import time

from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.services.optional.e2 import kpm_indication, sim_speed
from main.apps.cu_cp.services.optional.e2.subscription_registry import (
    RAN_FUNC_ID_KPM,
    RAN_FUNC_ID_RC,
    get_store,
)
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


logger = get_logger(__name__)


_SUPPORTED_SERVICE_MODELS = ("KPM", "RC")
_RAN_FUNC_ID_MAP = {"KPM": RAN_FUNC_ID_KPM, "RC": RAN_FUNC_ID_RC}


class E2SubscriptionActor:
    """OAI 對應：
    - create  ↔ E2AP RIC Subscription Request
    - delete  ↔ E2AP RIC Subscription Delete Request
    """

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def create(request: HttpRequest):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), status=400)

        sm = payload.get("service_model")
        if sm not in _SUPPORTED_SERVICE_MODELS:
            return error_response(
                f"service_model must be one of {_SUPPORTED_SERVICE_MODELS}",
                status=400,
            )
        action_def = payload.get("action_definition") or {}
        event_trigger = payload.get("event_trigger") or {}
        ric_req_id = payload.get("ric_req_id")

        if sm == "KPM":
            metrics = action_def.get("metrics") or []
            unsup = [m for m in metrics if m not in kpm_indication.supported_metrics()]
            if unsup:
                return error_response(
                    f"unsupported metric(s): {unsup}. supported: {kpm_indication.supported_metrics()}",
                    status=400,
                )

        sub = get_store().create(
            service_model=sm,
            ran_function_id=payload.get("ran_function_id") or _RAN_FUNC_ID_MAP[sm],
            action_definition=action_def,
            event_trigger=event_trigger,
            ric_req_id=ric_req_id,
        )

        # 立刻產一筆 indication 進 buffer（讓 xApp 第一次 poll 就有東西）
        if sm == "KPM":
            ind = kpm_indication.build_indication(sub)
            if ind:
                get_store().append_indication(sub["subscription_id"], ind)

        logger.info(
            "E2 Subscription created: id=%s sm=%s metrics=%s period=%dms",
            sub["subscription_id"], sm,
            action_def.get("metrics"), event_trigger.get("report_period_ms", 0),
        )
        return success_response(
            {
                "subscription_id": sub["subscription_id"],
                "ric_req_id": sub["ric_req_id"],
                "ran_function_id": sub["ran_function_id"],
                "status": "active",
            },
            "subscribed",
            status=201,
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def list(request: HttpRequest):
        """Adapter 重啟後 query 已有 subs 重啟 indication producer 用。

        回 active 訂閱的 subscription_id, ric_req_id, ran_function_id, action_definition,
        event_trigger — adapter 拿到就能還原 producer state。
        """
        subs = get_store().list_active()
        out = [
            {
                "subscription_id": s["subscription_id"],
                "service_model": s["service_model"],
                "ran_function_id": s["ran_function_id"],
                "ric_req_id": s.get("ric_req_id", {}),
                "action_definition": s.get("action_definition", {}),
                "event_trigger": s.get("event_trigger", {}),
                "created_at_ms": s.get("created_at_ms", 0),
            }
            for s in subs
        ]
        return success_response({"subscriptions": out, "count": len(out)})

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def delete(request: HttpRequest):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), status=400)
        sub_id = payload.get("subscription_id")
        if not sub_id:
            return error_response("subscription_id required", status=400)
        ok = get_store().delete(sub_id)
        if not ok:
            return error_response(f"unknown subscription_id {sub_id}", status=404)
        logger.info("E2 Subscription deleted: id=%s", sub_id)
        return success_response({"subscription_id": sub_id, "status": "deleted"}, "ok")


class E2IndicationActor:
    """OAI 對應 RIC Indication，但用 polling 取代 SCTP push。

    每次 poll：
      1. 看 subscription event_trigger.report_period_ms 決定要不要產新 indication
      2. drain buffer 把累積的 indications 全部回給 xApp
    """

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def poll(request: HttpRequest):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), status=400)
        sub_id = payload.get("subscription_id")
        if not sub_id:
            return error_response("subscription_id required", status=400)

        store = get_store()
        sub = store.get(sub_id)
        if sub is None:
            return error_response(f"unknown subscription_id {sub_id}", status=404)

        # 看是不是該產新 indication（按 event_trigger.report_period_ms）
        # 同步加速:report_period_ms 是 sim-time 約定,wall 上要 / sim_speed_x。
        # 例:speed=10x,period 1000(sim) → wall 100ms 就產一筆。
        period_ms = int(sub.get("event_trigger", {}).get("report_period_ms", 1000))
        speed = sim_speed.get_speed()
        effective_period_ms = period_ms / max(speed, 0.1)
        now_ms = int(time.time() * 1000)
        if now_ms - sub["last_indication_at_ms"] >= effective_period_ms:
            if sub["service_model"] == "KPM":
                ind = kpm_indication.build_indication(sub)
                if ind is not None:
                    store.append_indication(sub_id, ind)

        indications = store.drain_buffer(sub_id)
        return success_response(
            {
                "subscription_id": sub_id,
                "indications": indications,
                "count": len(indications),
            },
            "ok",
        )
