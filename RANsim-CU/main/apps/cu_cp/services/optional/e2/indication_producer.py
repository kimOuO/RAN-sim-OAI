"""Background producer task — 定期產生 KPM indication 推給訂閱的 WebSocket consumers。

對齊 OAI ref：
  - openair2/E2AP/RAN_FUNCTION/O-RAN/ran_func_kpm.c
    (KPM indication 由 OAI 內部 timer / event 產，我們用 asyncio loop 模擬)

設計：
  - 在 Django app ready() 時用 daemon thread 啟動一個 asyncio loop
  - Loop 每 100ms 掃 subscription_registry 裡所有「有 ws consumer 訂閱」的 sub
  - 看 sub 的 event_trigger.report_period_ms，決定要不要推新 indication
  - 對每個 active ws consumer 呼 push_indication
"""
from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

from main.apps.cu_cp.services.optional.e2 import kpm_indication
from main.apps.cu_cp.services.optional.e2.subscription_registry import get_store
from main.utils.logger import get_logger


logger = get_logger(__name__)


_thread: threading.Thread | None = None
_loop: asyncio.AbstractEventLoop | None = None
_stop = threading.Event()


async def _producer_coro() -> None:
    """主 producer loop：每 100ms 掃一次。"""
    logger.info("E2 indication producer started")
    while not _stop.is_set():
        try:
            await _tick()
        except Exception as e:  # pragma: no cover
            logger.exception("producer tick failed: %s", e)
        await asyncio.sleep(0.1)
    logger.info("E2 indication producer stopped")


async def _tick() -> None:
    store = get_store()
    sub_ids = store.list_ws_subscribed_ids()
    if not sub_ids:
        return
    now_ms = int(time.time() * 1000)
    for sub_id in sub_ids:
        sub = store.get(sub_id)
        if sub is None:
            continue
        period_ms = int(sub.get("event_trigger", {}).get("report_period_ms", 1000))
        if now_ms - sub["last_indication_at_ms"] < period_ms:
            continue
        # 產生 indication（KPM only；RC 之後再加）
        if sub["service_model"] != "KPM":
            continue
        ind: dict[str, Any] | None = await asyncio.get_event_loop().run_in_executor(
            None, _build_indication_safe, sub
        )
        if ind is None:
            continue
        # 更新 last_indication_at_ms（透過 store 內方法）
        store.append_indication(sub_id, ind)
        # 推給所有訂閱這個 sub 的 ws consumer
        for consumer in store.get_ws_consumers(sub_id):
            try:
                await consumer.push_indication(ind)
            except Exception as e:
                logger.warning("push fail consumer for sub=%s: %s", sub_id, e)


def _build_indication_safe(sub: dict[str, Any]) -> dict[str, Any] | None:
    """KPM indication build 內部會 query Django ORM，必須跑在 thread executor 內。"""
    try:
        return kpm_indication.build_indication(sub)
    except Exception as e:
        logger.exception("build_indication failed: %s", e)
        return None


def _run_loop() -> None:
    """Thread target：起 asyncio loop 跑 producer coroutine 直到 _stop。"""
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    try:
        _loop.run_until_complete(_producer_coro())
    finally:
        _loop.close()
        _loop = None


def start() -> None:
    """從 Django app config 的 ready() 呼這個。idempotent。"""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_run_loop, daemon=True, name="e2-ind-producer")
    _thread.start()


def stop() -> None:
    _stop.set()
