"""CU 端的劇本時鐘 —— 「現在是劇本的第幾毫秒」。

DU 是這個值的唯一真實來源(scene_tick × sim_dt_ms,就是 cached 通道查表的索引),
每個量測報告都會帶下來。CU 收到就更新這裡,之後任何地方建立事件(換手、RLF、重建)
都能直接蓋上「發生在劇本第幾秒」。

為什麼不由事件自己去推算:
  - 牆鐘換算要乘倍速,而倍速達成率不穩(實測設 30x 只達成 27.3x)
  - 歸檔原本把各視窗的 tick_count 累加來推算,報告一掉就失真
    (實測 8h 劇本一場少算 59%、另一場多算 12%)
  - RIC 觸發的換手根本不在量測處理流程裡,拿不到 window_seq

精度是一個 PM 視窗(預設 1 秒)—— offset_s 只要秒級,夠用。
沒收到過任何報告時回 None,呼叫端要能接受(不要拿 0 頂替,0 是合法的劇本時間)。
"""
from __future__ import annotations

import threading

_lock = threading.Lock()
_scene_sim_ms: int | None = None


def update(scene_sim_ms: int | None) -> None:
    """DU 報告帶來的劇本時鐘。None(舊版 DU)就不動,保留上一個已知值。"""
    global _scene_sim_ms
    if scene_sim_ms is None:
        return
    with _lock:
        _scene_sim_ms = int(scene_sim_ms)


def now_ms() -> int | None:
    with _lock:
        return _scene_sim_ms


def reset() -> None:
    """換一場 run 要歸零,否則新的一場會沿用上一場的時間。"""
    global _scene_sim_ms
    with _lock:
        _scene_sim_ms = None
