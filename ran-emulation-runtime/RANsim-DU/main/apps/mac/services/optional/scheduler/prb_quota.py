"""PRB quota store — per-cell slice-level PRB quota cap。

xApp 透過 E2 Control Style 2 / Action 6 (`control_slice_level_prb_quota`) 設定後，
DU MAC scheduler 在 allocate() 前用 max_prb/100 縮減該 cell 的 PRB pool。

State：in-memory dict per cell。Lost on container restart（跟 E2 subscription registry 同模式）。
xApp 偵測到 quota 被忘了應該重發 control。

對齊 OAI:
  - openair2/E2AP/RAN_FUNCTION/O-RAN/ran_func_rc.c::write_ctrl_rc_sm Style 2 / Action 6
  - 影響 DU 的 max_rbSize per slice（單 slice fixed）
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class PrbQuota:
    cell_id: str
    min_prb: int = 0       # 0-100，最低 PRB 比例（暫不差異化套用，xApp spec 註明）
    max_prb: int = 100     # 0-100，最高 PRB 比例（重點，影響 max_rbSize）
    dedicated_prb: int = 100  # 0-100，專屬 PRB 比例（暫不差異化）
    set_at_ms: int = 0
    set_by: str = ""        # 紀錄是誰下的（'xApp' / 'admin' / 'A1'）

    def cap_factor(self) -> float:
        """0.0~1.0 — DU scheduler n_prb_total × cap_factor 就是上限。"""
        return max(0, min(100, self.max_prb)) / 100.0


class _PrbQuotaStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._quotas: dict[str, PrbQuota] = {}   # cell_id → PrbQuota

    def set_quota(self, cell_id: str, *, min_prb: int, max_prb: int,
                  dedicated_prb: int, set_at_ms: int, set_by: str = "xApp") -> PrbQuota:
        q = PrbQuota(
            cell_id=cell_id,
            min_prb=int(min_prb),
            max_prb=int(max_prb),
            dedicated_prb=int(dedicated_prb),
            set_at_ms=set_at_ms,
            set_by=set_by,
        )
        with self._lock:
            self._quotas[cell_id] = q
        return q

    def clear(self, cell_id: str) -> None:
        with self._lock:
            self._quotas.pop(cell_id, None)

    def clear_all(self) -> int:
        """清空所有 cell 的 quota。Start Sim 用,避免上一輪 xApp 設的 cap 洩漏到本次劇本。"""
        with self._lock:
            n = len(self._quotas)
            self._quotas.clear()
            return n

    def get(self, cell_id: str) -> PrbQuota | None:
        with self._lock:
            return self._quotas.get(cell_id)

    def cap_factor(self, cell_id: str) -> float:
        """1.0 if no quota set；否則 max_prb/100。Scheduler 在排程前呼叫。"""
        q = self.get(cell_id)
        return q.cap_factor() if q else 1.0

    def list_all(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(q) for q in self._quotas.values()]


_store_singleton: _PrbQuotaStore | None = None


def get_store() -> _PrbQuotaStore:
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = _PrbQuotaStore()
    return _store_singleton
