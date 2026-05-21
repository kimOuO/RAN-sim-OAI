"""Sim speed runtime knob — auto-follow DU's `sim_speed_x`.

DU 是 sim-time 的唯一真實來源(它持有 wall_tick_ms + sim_dt_ms,sim_speed_x =
sim_dt_ms / wall_tick_ms)。CU 端要做 sim-time KPM 取樣就得跟 DU 同步,不應該
有獨立的速度狀態 — 否則 DU 改速度時 CU/adapter 會漂離。

設計:
  - 後台 thread 每 2s pull 一次 DU /TickController/read,cache `sim_speed_x`
  - get_speed() 純查 cache,沒有 HTTP cost
  - DU 暫時連不上保留 last-known 值,下輪 retry(不掉到 1.0)
  - 暴露 set_speed() 給 endpoint 做手動 override(測試 / 偶爾 Dashboard 手切),
    set 完 _override_until_ms 給 30s,期間 background pull 不覆蓋,過期後恢復跟隨。
"""
from __future__ import annotations

import threading
import time

import requests

from main.utils.env_loader import get_str
from main.utils.logger import get_logger


logger = get_logger(__name__)

_REFRESH_INTERVAL_SEC = 2.0
_OVERRIDE_TTL_MS = 30_000  # 手動 set 後保留 30s 不被 DU 覆蓋
_HTTP_TIMEOUT_SEC = 1.0

_lock = threading.Lock()
_sim_speed_x: float = 1.0
_override_until_ms: int = 0
_started = False
_started_lock = threading.Lock()


def _du_base_url() -> str:
    host = get_str("HTTP_DU_HOST")
    port = get_str("HTTP_DU_PORT", "8000")
    scheme = get_str("HTTP_DU_SCHEME", "http")
    if not host:
        return ""
    return f"{scheme}://{host}:{port}"


def _refresh_from_du() -> None:
    global _sim_speed_x
    base = _du_base_url()
    if not base:
        return
    try:
        r = requests.post(
            f"{base}/api/v0.1/DU/Tick/TickController/read",
            json={}, timeout=_HTTP_TIMEOUT_SEC,
        )
        data = (r.json() or {}).get("data") or {}
        new_speed = float(data.get("sim_speed_x", 1.0))
    except Exception:
        return  # 保留上次值
    new_speed = max(0.1, min(30.0, new_speed))
    now_ms = int(time.time() * 1000)
    with _lock:
        if now_ms < _override_until_ms:
            return  # 手動 override 還在 TTL 內,不蓋
        old = _sim_speed_x
        _sim_speed_x = new_speed
    if abs(old - new_speed) > 0.05:
        logger.info("KPM sim_speed_x (from DU): %.2fx -> %.2fx", old, new_speed)


def _refresher_loop() -> None:
    while True:
        try:
            _refresh_from_du()
        except Exception:
            logger.exception("sim_speed refresh failed")
        time.sleep(_REFRESH_INTERVAL_SEC)


def _ensure_started() -> None:
    global _started
    with _started_lock:
        if _started:
            return
        threading.Thread(target=_refresher_loop, daemon=True, name="cu-sim-speed").start()
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
        logger.info("KPM sim_speed_x (manual override 30s): %.2fx -> %.2fx", old, clamped)
    return clamped


def get_speed() -> float:
    _ensure_started()
    with _lock:
        return _sim_speed_x
