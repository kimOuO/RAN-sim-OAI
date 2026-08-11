"""HTTP client for sim CU REST API.

Skeleton (P2.7a): only fetch_e2_node_id() implemented + last-error tracking
for /Status/read.

P2.8 will add:
  - call_subscription_create()
  - call_subscription_delete()
  - poll_indication()
  - call_control_request()
"""
from __future__ import annotations

import threading
import time
from typing import Any

import requests

from main.utils.env_loader import get_str
from main.utils.logger import get_logger

logger = get_logger(__name__)

_HTTP_TIMEOUT_SEC = 5.0


class _BridgeState:
    """Thread-safe last-call tracker — read by /Status/read."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.last_e2_node_id_at_ms = 0
        self.last_error = ""
        self.last_error_at_ms = 0

    def mark_success(self) -> None:
        with self._lock:
            self.last_e2_node_id_at_ms = int(time.time() * 1000)
            self.last_error = ""

    def mark_error(self, err: str) -> None:
        with self._lock:
            self.last_error = err
            self.last_error_at_ms = int(time.time() * 1000)

    def snapshot(self) -> dict:
        with self._lock:
            # AG14: error stale 超過 60s 就 hide — 避免一次性的 transient 錯誤
            # (例如 CU 重啟 1 秒撞到 connection reset) 之後一直停在 status 上,
            # 讓人誤以為現在還在壞。E2 Setup 是一次性的, 後續不再 fetch CU,
            # 所以 error timestamp 不會被覆蓋, 必須在 status read 端主動 stale-out.
            now_ms = int(time.time() * 1000)
            err = self.last_error
            err_at = self.last_error_at_ms
            if err and err_at and (now_ms - err_at) > 60_000:
                err = ""
            return {
                "cu_url": get_str("SIM_CU_URL", ""),
                "last_e2_node_id_at_ms": self.last_e2_node_id_at_ms,
                "last_error": err,
                "last_error_at_ms": err_at,
            }


_state = _BridgeState()


def get_state_snapshot() -> dict:
    return _state.snapshot()


class SubNotFoundError(RuntimeError):
    """sim CU 不認得這個 subscription_id（被 sim 重啟後 wipe 過，producer 該停）。"""


def _post_sim(path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    base = get_str("SIM_CU_URL", "")
    if not base:
        _state.mark_error("SIM_CU_URL env var unset")
        return None
    url = f"{base.rstrip('/')}{path}"
    try:
        resp = requests.post(url, json=payload, timeout=_HTTP_TIMEOUT_SEC)
        if resp.status_code == 404:
            # 試讀 body 看是不是 unknown subscription_id（不是 endpoint 不存在）
            try:
                msg = resp.json().get("message", "")
            except Exception:
                msg = ""
            if "unknown subscription_id" in msg.lower() or "subscription" in msg.lower():
                raise SubNotFoundError(msg or f"{path} 404")
            _state.mark_error(f"{path} HTTP 404 ({msg})")
            return None
        if resp.status_code >= 500:
            _state.mark_error(f"{path} HTTP {resp.status_code}")
            return None
        body = resp.json()
        if not body.get("success"):
            logger.warning("sim %s non-success: %s", path, body.get("message"))
            return None
        _state.mark_success()
        return body.get("data") or {}
    except requests.RequestException as exc:
        _state.mark_error(repr(exc))
        logger.warning("sim CU %s failed: %s", path, exc)
        return None


def fetch_e2_node_id() -> dict[str, Any] | None:
    """Pull globalE2node-ID + RAN function inventory from sim CU.

    Adapter calls this once at startup before sending E2 Setup Request.
    Returns parsed payload or None on failure.
    """
    return _post_sim("/api/v0.1/CU/E2/E2NodeId/read", {})


def call_subscription_create(payload: dict[str, Any]) -> dict[str, Any] | None:
    """POST /CU/E2/Subscription/create → returns {subscription_id, ...}."""
    return _post_sim("/api/v0.1/CU/E2/Subscription/create", payload)


def call_subscription_delete(subscription_id: str) -> dict[str, Any] | None:
    return _post_sim("/api/v0.1/CU/E2/Subscription/delete",
                     {"subscription_id": subscription_id})


def list_subscriptions() -> list[dict[str, Any]]:
    """Adapter 啟動恢復用 — 拿 sim CU 端所有 active subs。"""
    data = _post_sim("/api/v0.1/CU/E2/Subscription/list", {})
    if data is None:
        return []
    return data.get("subscriptions") or []


def fetch_full_kpm() -> dict[str, Any] | None:
    """POST /CU/E2/E2FullReporter/read → 完整 E2_data_example.md 格式 snapshot。

    E2SM-DTFULLKPM(ran_func 5)indication producer 用。
    """
    return _post_sim("/api/v0.1/CU/E2/E2FullReporter/read", {})


def poll_indication(subscription_id: str) -> dict[str, Any] | None:
    """POST /CU/E2/Indication/poll → returns {indications: [...], count}."""
    return _post_sim("/api/v0.1/CU/E2/Indication/poll",
                     {"subscription_id": subscription_id})


def call_control_request(payload: dict[str, Any]) -> dict[str, Any] | None:
    """POST /CU/E2/Control/request — adapter → sim CU forward RC control.

    payload e.g.:
      {action: "handover", ngap_id, f1ap_id, target_cgi, ...}
      {action: "prb_quota", min_prb, max_prb, dedicated_prb, ...}
    """
    return _post_sim("/api/v0.1/CU/E2/Control/request", payload)


def call_anr_control(payload: dict[str, Any]) -> dict[str, Any] | None:
    """POST /CU/E2/Anr/control — adapter → sim CU forward E2SM-ANR SON trigger.

    payload: {sim_action:'anr_son_trigger', request:{requestType, sourceCellId, ...}}
    """
    return _post_sim("/api/v0.1/CU/E2/Anr/control", payload)
