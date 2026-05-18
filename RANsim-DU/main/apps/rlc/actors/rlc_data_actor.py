"""RLC 資料注入(模擬 F1-U 進來的 SDU)/ buffer status 查詢。"""
from __future__ import annotations

import json
import time

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.rlc.serializers.rlc_entity_serializers import (
    RlcInjectSduBatchSerializer,
    RlcInjectSduSerializer,
)
from main.apps.rlc.services.optional.entities import factory as entity_factory
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


def _now_ms() -> int:
    return int(time.time() * 1000)


class RlcDataController:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def inject_sdu(request):
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        ser = RlcInjectSduSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, http_status=400)

        v = ser.validated_data
        entity = entity_factory.lookup(v["ue_id"], v["bearer_type"], v["bearer_id"])
        if entity is None:
            return error_response("RLC entity not found", http_status=404)

        sdu_id = entity.recv_sdu(v["sdu_bytes"])
        return success_response({"sdu_id": sdu_id, "bo": entity.buffer_status()}, "Injected")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def inject_sdu_batch(request):
        """AL: 接受 N 個 sub-SDU + per-packet ts_offset_us, 還原 enqueue_ts_ms 寫進 RLC.

        對齊 OAI per-packet inject — UE traffic_gen tick window 內每個 1500B packet
        都有自己的 wall-clock enqueue 時戳, 解決三項 KPM (Thp/Delay/Volume) 失真.
        """
        try:
            payload = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), http_status=400)

        ser = RlcInjectSduBatchSerializer(data=payload)
        if not ser.is_valid():
            # AL debug: dump 部分 payload + errors 看為何 reject.
            preview = {k: v for k, v in payload.items() if k != "items"}
            preview["items_len"] = len(payload.get("items", []) or [])
            if preview["items_len"] > 0:
                preview["items_first"] = (payload.get("items") or [None])[0]
            logger.warning(
                "inject_sdu_batch validation failed: preview=%s errors=%s",
                preview, ser.errors,
            )
            return error_response("Validation failed", ser.errors, http_status=400)
        v = ser.validated_data

        entity = entity_factory.lookup(v["ue_id"], v["bearer_type"], v["bearer_id"])
        if entity is None:
            return error_response("RLC entity not found", http_status=404)

        items = v["items"]
        if not items:
            return success_response({"sdu_ids": [], "bo": entity.buffer_status()}, "Empty batch")

        # 還原 wall-clock enqueue_ts_ms.
        # ts_offset_us=0 是 window 開頭 (即「現在 - window_ms」前), max offset 是「現在」.
        # 若 window_ms=100, offset=0 → enqueue 100ms 前. offset=100000 → enqueue 現在.
        now_ms = _now_ms()
        window_ms = v["window_ms"]
        sdu_ids: list[int] = []
        for item in items:
            offset_ms = item["ts_offset_us"] / 1000.0
            enqueue_ts = int(now_ms - (window_ms - offset_ms))
            sdu_id = entity.recv_sdu(item["sdu_bytes"], enqueue_ts_ms=enqueue_ts)
            sdu_ids.append(sdu_id)
        return success_response(
            {"sdu_ids": sdu_ids, "n_items": len(items), "bo": entity.buffer_status()},
            f"Injected {len(items)} sub-SDU",
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read_buffer_status(request):
        out = []
        for (ue, btype, bid), ent in entity_factory.all_entities():
            out.append({
                "ue_id": ue, "bearer_type": btype, "bearer_id": bid,
                "mode": ent.mode, "buffer_occupancy": ent.buffer_status(),
            })
        return success_response(out, "OK")
