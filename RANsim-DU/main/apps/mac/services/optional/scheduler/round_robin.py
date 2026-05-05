"""Round-Robin scheduler — 平均分 PRB,僅作為 PF fallback。"""
from __future__ import annotations

from typing import Any


class RoundRobinScheduler:
    def __init__(self) -> None:
        self._cursor: dict[str, int] = {}

    def reset(self) -> None:
        self._cursor.clear()

    def allocate(
        self,
        *,
        gnb_name: str,
        ues_on_gnb: list[dict[str, Any]],
        n_prb_total: int,
    ) -> dict[str, int]:
        if not ues_on_gnb:
            return {}
        share = max(1, n_prb_total // len(ues_on_gnb))
        rb_alloc = {ue["id"]: share for ue in ues_on_gnb}
        leftover = n_prb_total - share * len(ues_on_gnb)
        cursor = self._cursor.get(gnb_name, 0)
        for i in range(leftover):
            uid = ues_on_gnb[(cursor + i) % len(ues_on_gnb)]["id"]
            rb_alloc[uid] += 1
        self._cursor[gnb_name] = (cursor + leftover) % len(ues_on_gnb)
        return rb_alloc
