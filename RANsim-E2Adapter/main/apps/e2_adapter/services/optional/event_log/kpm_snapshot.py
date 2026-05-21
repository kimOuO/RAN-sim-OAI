"""KPM snapshot ring — 紀錄 adapter 從 sim CU pull 的最新 KPM measurement 給 Dashboard 顯示。

- 為每個 UE 保留 latest snapshot dict (metric → {value, unit, ts_ms})
- 歷史時序 ring buffer (max _MAX_HISTORY) 給 sparkline / chart 用
- snapshot 是 adapter pull 完原始 payload 立刻記下，跟送給 RIC 的 PDU 同源

跟 event_log/ring 是分開的（事件 vs 數值），避免一個 ring 混兩種資料型態。
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Deque

_MAX_HISTORY = 60          # 每個 UE 每 metric 保 60 筆時序（1Hz × 1分鐘）
_MAX_RECENT = 200          # 全域最近 N 筆 (跨所有 UE) 給 timeline

# latest_snapshot() 的 UE 過期視窗 — 最新 metric ts 超過這時間就不出現在
# Dashboard 上(_latest 內仍保留,history 查還用得到)。30s 對齊 1Hz polling
# 的「最近沒有資料來」直覺。
_SNAPSHOT_STALE_AFTER_MS = 30_000


class _KpmRing:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # latest by UE+metric: ue_id → metric_name → {value, unit, ts_ms}
        self._latest: dict[str, dict[str, dict[str, Any]]] = {}
        # history per UE+metric: (ue_id, metric_name) → deque[{value, ts_ms}]
        self._history: dict[tuple[str, str], Deque[dict[str, Any]]] = {}
        # recent flat list: 最近 N 筆 (跨所有 UE)
        self._recent: Deque[dict[str, Any]] = deque(maxlen=_MAX_RECENT)
        # bookkeeping
        self._last_update_ms = 0
        self._total_indications = 0

    def append_indication(self, sub_id: str, indication: dict[str, Any]) -> None:
        """從 sim CU 完整 indication payload 抽 metric 並寫進 ring。"""
        ind_msg = indication.get("indication_message") or {}
        ue_lst = ind_msg.get("ue_meas_report_lst") or []
        ts_ms = int(time.time() * 1000)

        with self._lock:
            self._total_indications += 1
            self._last_update_ms = ts_ms
            for ue in ue_lst:
                ue_id = ue.get("ue_id") or "unknown"
                serving_cell = ue.get("serving_cell") or ""
                meas_data = ue.get("meas_data_lst") or []
                if ue_id not in self._latest:
                    self._latest[ue_id] = {}
                for m in meas_data:
                    name = m.get("name")
                    if not name:
                        continue
                    value = m.get("value")
                    unit = m.get("unit") or ""
                    self._latest[ue_id][name] = {
                        "value": value,
                        "unit": unit,
                        "ts_ms": ts_ms,
                        "serving_cell": serving_cell,
                    }
                    # history per UE+metric
                    key = (ue_id, name)
                    if key not in self._history:
                        self._history[key] = deque(maxlen=_MAX_HISTORY)
                    self._history[key].append({"ts_ms": ts_ms, "value": value})
                    self._recent.append({
                        "ts_ms": ts_ms, "ue_id": ue_id, "metric": name,
                        "value": value, "unit": unit, "serving_cell": serving_cell,
                        "sub_id": sub_id,
                    })

    def latest_snapshot(self) -> dict[str, Any]:
        """Dashboard 主面板用 — table by UE × metric。

        只列「最近 _SNAPSHOT_STALE_AFTER_MS(30s)有 indication 來」的 UE。
        _latest 內舊資料仍保留,history 查詢還能拉到,但 Dashboard 不會看到
        死掉的 UE(例如上一場 scenario 的、52 小時前 demo 殘留 sub)。
        """
        now_ms = int(time.time() * 1000)
        cutoff_ms = now_ms - _SNAPSHOT_STALE_AFTER_MS
        with self._lock:
            ues_out = []
            for ue_id, metrics in self._latest.items():
                if not metrics:
                    continue
                latest_ts = max(m.get("ts_ms", 0) for m in metrics.values())
                if latest_ts < cutoff_ms:
                    continue  # UE 沉默太久,當作離線不顯示
                ues_out.append({
                    "ue_id": ue_id,
                    "metrics": [
                        {
                            "name": m_name,
                            "value": m_data["value"],
                            "unit": m_data["unit"],
                            "ts_ms": m_data["ts_ms"],
                            "serving_cell": m_data.get("serving_cell", ""),
                        }
                        for m_name, m_data in metrics.items()
                    ],
                })
            return {
                "ues": ues_out,
                "last_update_ms": self._last_update_ms,
                "total_indications": self._total_indications,
            }

    def history_for(self, ue_id: str, metric: str, limit: int = 60) -> list[dict[str, Any]]:
        with self._lock:
            dq = self._history.get((ue_id, metric))
            if not dq:
                return []
            return list(dq)[-limit:]

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._recent)[-limit:]


_ring = _KpmRing()


def get_ring() -> _KpmRing:
    return _ring
