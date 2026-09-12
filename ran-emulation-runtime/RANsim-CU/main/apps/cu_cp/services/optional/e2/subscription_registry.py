"""E2 Subscription registry — 對齊 OAI E2AP RIC Subscription 模式。

OAI ref:
  - openair2/E2AP/RAN_FUNCTION/init_ran_func.c (RIC Subscription handler)
  - openair2/E2AP/RAN_FUNCTION/O-RAN/ran_func_kpm_subs.c (KPM subs)
  - openair2/E2AP/RAN_FUNCTION/O-RAN/ran_func_rc.c (RC subs/control)

In-memory subscription state（per-process singleton）。每個 active subscription:
  - subscription_id: 給 xApp 的 handle
  - service_model: 'KPM' | 'RC'
  - ran_function_id: KPM=2, RC=3
  - action_definition: metrics + report_period_ms + ue_filter
  - event_trigger: format + report_period_ms
  - ric_req_id: { requestor_id, instance_id }（OAI E2AP message 內的 ID）
  - last_indication_at_ms: 上次推 indication 的時間
  - buffered_indications: List[dict] — pending indications 等 xApp poll
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any


# OAI 對應的 RAN Function IDs（由 E2 Setup 階段 RIC 分配，這裡 hardcode 對齊 OAI 預設）
RAN_FUNC_ID_KPM = 2
RAN_FUNC_ID_RC = 3


class _SubscriptionStore:
    """Thread-safe singleton store。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # subscription_id → subscription dict
        self._subs: dict[str, dict[str, Any]] = {}
        # 每個 subscription 的 indication buffer（FIFO，最多保 100 筆）
        self._buffers: dict[str, list[dict[str, Any]]] = {}
        # WebSocket consumers：subscription_id → set of consumer instances
        # （consumer 是 channels AsyncJsonWebsocketConsumer，有 send_json）
        self._ws_consumers: dict[str, set[Any]] = {}

    def create(
        self,
        *,
        service_model: str,
        ran_function_id: int,
        action_definition: dict[str, Any],
        event_trigger: dict[str, Any],
        ric_req_id: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        sub_id = f"sub-{uuid.uuid4().hex[:12]}"
        sub = {
            "subscription_id": sub_id,
            "service_model": service_model,
            "ran_function_id": ran_function_id,
            "action_definition": action_definition,
            "event_trigger": event_trigger,
            # ricInstanceID 在 E2AP 是 INTEGER (0..65535)；timestamp 會超 → 取 mod
            "ric_req_id": ric_req_id or {"requestor_id": 1, "instance_id": int(time.time()) & 0xFFFF},
            "created_at_ms": int(time.time() * 1000),
            "last_indication_at_ms": 0,
            "status": "active",
        }
        with self._lock:
            self._subs[sub_id] = sub
            self._buffers[sub_id] = []
        _persist_save(sub)          # 層1:跨重啟存活(失敗不擋建立)
        return sub

    def delete(self, subscription_id: str) -> bool:
        with self._lock:
            if subscription_id not in self._subs:
                return False
            del self._subs[subscription_id]
            self._buffers.pop(subscription_id, None)
        _persist_delete(subscription_id)
        return True

    def get(self, subscription_id: str) -> dict[str, Any] | None:
        with self._lock:
            sub = self._subs.get(subscription_id)
            return dict(sub) if sub else None

    def list_active(
        self,
        service_model: str | None = None,
    ) -> list[dict[str, Any]]:
        """Snapshot 所有活的 subscription（給 indication producer 看誰要推）。"""
        with self._lock:
            return [
                dict(s)
                for s in self._subs.values()
                if service_model is None or s["service_model"] == service_model
            ]

    def append_indication(self, subscription_id: str, indication: dict[str, Any]) -> None:
        with self._lock:
            if subscription_id not in self._buffers:
                return
            buf = self._buffers[subscription_id]
            buf.append(indication)
            # FIFO trim: 最多保 100 筆，太久沒 poll 的就丟
            if len(buf) > 100:
                del buf[: len(buf) - 100]
            sub = self._subs.get(subscription_id)
            if sub is not None:
                sub["last_indication_at_ms"] = int(time.time() * 1000)

    def drain_buffer(self, subscription_id: str) -> list[dict[str, Any]]:
        """xApp poll 時拿走全部 buffered indications。"""
        with self._lock:
            buf = self._buffers.get(subscription_id, [])
            self._buffers[subscription_id] = []
            return buf

    # ── WebSocket consumer 管理（channels 用） ──────────────────────

    def add_ws_consumer(self, subscription_id: str, consumer: Any) -> bool:
        """xApp WebSocket 連上後 register。回 True 表示 sub 存在。"""
        with self._lock:
            if subscription_id not in self._subs:
                return False
            self._ws_consumers.setdefault(subscription_id, set()).add(consumer)
            return True

    def remove_ws_consumer(self, consumer: Any) -> None:
        """ws.disconnect 時移除。掃所有 sub 找這個 consumer。"""
        with self._lock:
            for s in self._ws_consumers.values():
                s.discard(consumer)

    def get_ws_consumers(self, subscription_id: str) -> list[Any]:
        with self._lock:
            return list(self._ws_consumers.get(subscription_id, ()))

    def list_ws_subscribed_ids(self) -> list[str]:
        """回所有「至少有一個 ws consumer 在訂閱」的 sub_id（producer 用來決定誰要推）。"""
        with self._lock:
            return [sid for sid, cs in self._ws_consumers.items() if cs]


# 全域單例
def _persist_save(sub: dict[str, Any]) -> None:
    try:
        from main.apps.cu_cp.models.e2_subscription import E2Subscription
        E2Subscription.objects.update_or_create(
            subscription_id=sub["subscription_id"],
            defaults=dict(
                service_model=sub["service_model"],
                ran_function_id=sub["ran_function_id"],
                action_definition=sub["action_definition"],
                event_trigger=sub["event_trigger"],
                ric_req_id=sub.get("ric_req_id") or {},
                created_at_ms=sub.get("created_at_ms", 0),
                status=sub.get("status", "active"),
            ))
    except Exception as exc:                      # DB 未就緒等 — 不擋 wire 行為
        import logging; logging.getLogger(__name__).warning("E2 sub persist failed: %s", exc)


def _persist_delete(sub_id: str) -> None:
    try:
        from main.apps.cu_cp.models.e2_subscription import E2Subscription
        E2Subscription.objects.filter(subscription_id=sub_id).delete()
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("E2 sub unpersist failed: %s", exc)


def restore_from_db() -> int:
    """CU 啟動時把 DB 裡的訂閱回載進 singleton(indication producer 啟動前呼叫)。

    回載後 adapter 的 sub registry poll 看到非空 → 不觸發 Y1 E2 Reset,
    RIC 端訂閱與 sub_id 全部原樣續用,indication 下一週期自動續流。
    """
    try:
        from main.apps.cu_cp.models.e2_subscription import E2Subscription
        rows = list(E2Subscription.objects.filter(status="active"))
    except Exception as exc:
        import logging; logging.getLogger(__name__).warning("E2 sub restore failed: %s", exc)
        return 0
    n = 0
    with _store._lock:
        for r in rows:
            if r.subscription_id in _store._subs:
                continue
            _store._subs[r.subscription_id] = {
                "subscription_id": r.subscription_id,
                "service_model": r.service_model,
                "ran_function_id": r.ran_function_id,
                "action_definition": r.action_definition,
                "event_trigger": r.event_trigger,
                "ric_req_id": r.ric_req_id,
                "created_at_ms": r.created_at_ms,
                "last_indication_at_ms": 0,
                "status": r.status,
            }
            _store._buffers[r.subscription_id] = []
            n += 1
    return n


_store = _SubscriptionStore()


def get_store() -> _SubscriptionStore:
    return _store
