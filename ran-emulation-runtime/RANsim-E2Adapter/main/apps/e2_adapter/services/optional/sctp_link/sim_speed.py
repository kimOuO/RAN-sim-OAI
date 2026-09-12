"""Sim speed runtime knob for e2adapter — auto-follow sim CU.

CU 端的 sim_speed 已經 auto-pull DU,adapter 再 pull CU 一手,就形成 DU → CU
→ adapter 的同步鏈,DU 改速度時最久 ~4s wall 全鏈路收斂(兩個 2s cache)。

設計同 CU 那邊:
  - background thread 每 2s GET CU /E2/KpmSpeed/read
  - get_speed() 純查 cache
  - manual override 30s TTL
"""
from __future__ import annotations

import threading
import time

import requests

from main.utils.env_loader import get_str
from main.utils.logger import get_logger


logger = get_logger(__name__)

_REFRESH_INTERVAL_SEC = 2.0
_OVERRIDE_TTL_MS = 30_000
_HTTP_TIMEOUT_SEC = 1.0

_lock = threading.Lock()
_sim_speed_x: float = 1.0
_override_until_ms: int = 0
_started = False
_started_lock = threading.Lock()


def _refresh_from_cu() -> None:
    global _sim_speed_x
    base = get_str("SIM_CU_URL", "")
    if not base:
        return
    try:
        r = requests.post(
            f"{base}/api/v0.1/CU/E2/KpmSpeed/read",
            json={}, timeout=_HTTP_TIMEOUT_SEC,
        )
        data = (r.json() or {}).get("data") or {}
        new_speed = float(data.get("sim_speed_x", 1.0))
    except Exception:
        return
    new_speed = max(0.1, min(30.0, new_speed))
    now_ms = int(time.time() * 1000)
    with _lock:
        if now_ms < _override_until_ms:
            return
        old = _sim_speed_x
        _sim_speed_x = new_speed
    if abs(old - new_speed) > 0.05:
        logger.info("adapter sim_speed_x (from CU): %.2fx -> %.2fx", old, new_speed)


def _refresher_loop() -> None:
    while True:
        try:
            _refresh_from_cu()
        except Exception:
            logger.exception("sim_speed refresh failed")
        time.sleep(_REFRESH_INTERVAL_SEC)


def _ensure_started() -> None:
    global _started
    with _started_lock:
        if _started:
            return
        threading.Thread(target=_refresher_loop, daemon=True, name="adapter-sim-speed").start()
        _started = True


def set_speed(speed_x: float) -> float:
    """手動 override — 30s 內 background pull 不會覆蓋。"""
    global _sim_speed_x, _override_until_ms
    clamped = max(0.1, min(30.0, float(speed_x)))
    with _lock:
        old = _sim_speed_x
        _sim_speed_x = clamped
        _override_until_ms = int(time.time() * 1000) + _OVERRIDE_TTL_MS
    if abs(old - clamped) > 1e-3:
        logger.info("adapter sim_speed_x (manual override 30s): %.2fx -> %.2fx", old, clamped)
    return clamped


def get_speed() -> float:
    _ensure_started()
    with _lock:
        return _sim_speed_x
