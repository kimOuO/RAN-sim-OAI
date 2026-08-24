"""ANR v10 的歷史統計層 —— baseline 與 trendLast30Min 的來源。

v10 幾乎每題的判準都是「相對 baseline 的變化」而非絕對值,並要求
`trendLast30Min` 六窗序列做持續性判定(全域限制 L4:不得由單一窗口值觸發)。
E2 本身只送當下快照,這兩者必須由 xApp 或 E2 節點側自行累積 ——
本卷把它放在觀測資料裡,所以 sim 要負責產生。

定義(本檔為權威,文件與此同步):
  trendLast30Min — 最近 6 個 5 分鐘窗的取樣值(舊→新)。不足 6 筆時補當前值,
                   讓 xApp 的持續性判定不會因為剛啟動就誤判「趨勢上升」。
  baseline       — 30 分鐘之前所有取樣的中位數;沒有更舊的樣本時退回最舊一筆。
                   用中位數不用平均:病發作時的尖峰不該把 baseline 一起拉高。

取樣節流為每 _SAMPLE_INTERVAL_SEC 一筆 —— adapter 每秒拉一次 indication,
不節流的話 30 分鐘會存 1800 筆,而六窗只需要 6 筆。
"""
from __future__ import annotations

import statistics
import threading
import time
from collections import deque
from typing import Any

_SAMPLE_INTERVAL_SEC = 300.0     # 5 分鐘一窗
_WINDOWS = 6                     # trendLast30Min = 6 窗 = 30 分鐘
_MAX_SAMPLES = 288               # 保 24 小時(288 × 5min),給 baseline 用
_BASELINE_AGE_SEC = 1800.0       # 30 分鐘之前的樣本才算「歷史」


class _Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._d: dict[str, deque[tuple[float, float]]] = {}

    def observe(self, key: str, value: float, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        with self._lock:
            dq = self._d.get(key)
            if dq is None:
                dq = self._d[key] = deque(maxlen=_MAX_SAMPLES)
            if dq and (now - dq[-1][0]) < _SAMPLE_INTERVAL_SEC:
                return                      # 節流:同一窗內只留第一筆
            dq.append((now, float(value)))

    def trend(self, key: str, current: float) -> list[float]:
        with self._lock:
            dq = self._d.get(key)
            vals = [v for _t, v in dq][-_WINDOWS:] if dq else []
        # 不足六窗補當前值(舊→新);避免剛啟動時被讀成「從 0 爬升」
        while len(vals) < _WINDOWS:
            vals.insert(0, round(float(current), 3))
        return [round(v, 3) for v in vals]

    def baseline(self, key: str, current: float, now: float | None = None) -> float:
        now = now if now is not None else time.time()
        with self._lock:
            dq = self._d.get(key)
            if not dq:
                return round(float(current), 3)
            old = [v for t, v in dq if (now - t) >= _BASELINE_AGE_SEC]
            if old:
                return round(statistics.median(old), 3)
            return round(dq[0][1], 3)       # 還沒有夠舊的 → 用最舊一筆

    def reset(self) -> None:
        with self._lock:
            self._d.clear()


_store = _Store()


def get_store() -> _Store:
    return _store


def metric(key: str, current: float | None, unit: str) -> dict[str, Any]:
    """把一個純量包成 v10 的指標物件。

    unit ∈ {PerMin, Pct, Mbps, Mbit, Ms} —— v10 的鍵名字尾隨單位變化
    (currentPerMin / currentPct / currentMbps / currentMbit / currentMs),
    速率語意的定義域由頂層 granularityPeriod 給定。
    """
    if current is None:
        current = 0.0
    cur = round(float(current), 3)
    _store.observe(key, cur)
    return {
        f"current{unit}": cur,
        f"baseline{unit}": _store.baseline(key, cur),
        "trendLast30Min": _store.trend(key, cur),
    }
