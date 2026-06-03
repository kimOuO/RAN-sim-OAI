"""P1 (2026-06-01) — DU achieved_speed_x 的背景快取。

問題:traffic_gen 過去用 profile 裡「設定的」sim_speed_x(例如 10)放大注入量,
但 DU 在負載下實際只跑到 achieved(例如 6.7)。設定 > 實際 → 慢性過量注入
(注入:排空 = 10:6.7 ≈ 1.49×)→ throughput / buffer / delay 全被墊高失真。

修法:讓 traffic_gen 改讀 DU「實際達成」的 achieved_speed_x(P0a 暴露),而不是
相信沒人兌現的設定值。3x 無漂移時 achieved == 設定 → 注入量位元級相同 → 不破壞
已對齊 OAI 的校正;只有在高倍速漂移時才修正過量注入。

設計鏡像 e2adapter/CU 的 sim_speed.py:
  - lazy-start 一條 daemon thread,每 _REFRESH_INTERVAL_SEC 從 DU 拉 achieved
  - get_achieved_speed() 純查 cache(不在 inject 熱路徑打 HTTP)
  - 拉不到 / 尚未量到(DU 回 0.0)→ cache 維持 0.0,caller 自行 fallback 到設定值
"""
from __future__ import annotations

import logging
import threading
import time

import requests
from django.conf import settings


logger = logging.getLogger(__name__)

_REFRESH_INTERVAL_SEC = 1.5
_HTTP_TIMEOUT_SEC = 1.0

_lock = threading.Lock()
_achieved_speed_x: float = 0.0
_started = False
_started_lock = threading.Lock()


def _refresh_from_du() -> None:
    global _achieved_speed_x
    base = getattr(settings, "SIM_DU_URL", "").rstrip("/")
    if not base:
        return
    try:
        r = requests.post(
            f"{base}/api/v0.1/DU/Tick/TickController/read",
            json={}, timeout=_HTTP_TIMEOUT_SEC,
        )
        data = (r.json() or {}).get("data") or {}
        new_val = float(data.get("achieved_speed_x", 0.0) or 0.0)
    except Exception:
        return
    new_val = max(0.0, min(30.0, new_val))
    with _lock:
        _achieved_speed_x = new_val


def _refresher_loop() -> None:
    while True:
        try:
            _refresh_from_du()
        except Exception:
            logger.exception("achieved sim_speed refresh failed")
        time.sleep(_REFRESH_INTERVAL_SEC)


def _ensure_started() -> None:
    global _started
    with _started_lock:
        if _started:
            return
        threading.Thread(
            target=_refresher_loop, daemon=True, name="ue-achieved-sim-speed",
        ).start()
        _started = True


def get_achieved_speed() -> float:
    """回傳 DU 實際達成倍速;0.0 = 尚未量到(剛啟動 / 拉不到)→ caller 該 fallback 設定值。"""
    _ensure_started()
    with _lock:
        return _achieved_speed_x
