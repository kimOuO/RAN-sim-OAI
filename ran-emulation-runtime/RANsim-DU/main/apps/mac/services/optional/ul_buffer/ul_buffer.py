"""UL 流量緩衝 + drain — 最小可用 UL 模型(對齊 OAI 有真 UL 流量,但 OAI 無 UL delay 故不做)。

DL 路徑:traffic_gen → RLC SDU → scheduler → slot 引擎(含 delay)。
UL 路徑(本模組):traffic_gen 推 UL 需求 bytes → 每 UE 累積 → tick_runner 用 UL 時隙容量 drain
                  → 真 ul_bytes / prb_ul 餵 pm_aggregator(取代舊的 DL÷5 代理)。

刻意不做 UL delay / UL HARQ / BSR / grant 訊令 —— OAI KPM 也沒報 RlcSduDelayUl,
對照只需 UEThpUl / RRU_PrbTotUl / DRB_PdcpSduVolumeUL。
"""
from __future__ import annotations

import math
import threading

_lock = threading.Lock()
_pending: dict[str, int] = {}   # ue_id → 待傳 UL bytes(backlog)


def report(ue_id: str, n_bytes: int) -> int:
    """traffic_gen 報本 tick 的 UL 需求 bytes,累積進 backlog。回傳累積後總量。"""
    if n_bytes <= 0:
        return _pending.get(ue_id, 0)
    with _lock:
        _pending[ue_id] = _pending.get(ue_id, 0) + int(n_bytes)
        return _pending[ue_id]


def drain(ue_id: str, capacity_bytes: int, bytes_per_prb: float) -> tuple[int, int]:
    """用本 tick UL 容量排空 backlog。回傳 (drained_bytes, prb_used)。

    capacity_bytes = UL 時隙容量(滿 PRB);bytes_per_prb = 一個 PRB 本 tick 在 UL 時隙能載的 bytes。
    prb_used = 排空量實際用掉的 PRB 數(向上取整),即 RRU_PrbTotUl 的來源。
    """
    with _lock:
        pend = _pending.get(ue_id, 0)
        drained = min(pend, max(0, int(capacity_bytes)))
        _pending[ue_id] = pend - drained
    prb = int(math.ceil(drained / bytes_per_prb)) if bytes_per_prb > 0 and drained > 0 else 0
    return drained, prb


def pending(ue_id: str) -> int:
    with _lock:
        return _pending.get(ue_id, 0)


def clear() -> int:
    """Start Sim 清空(對齊 clean-scene-reset,避免跨 session UL backlog 漏)。"""
    with _lock:
        n = len(_pending)
        _pending.clear()
        return n
