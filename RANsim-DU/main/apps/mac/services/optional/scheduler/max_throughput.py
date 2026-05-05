"""Max-Throughput scheduler — greedy by SINR,壓縮給高 SINR UE。"""
from __future__ import annotations

from typing import Any


class MaxThroughputScheduler:
    def __init__(self, max_share: float = 0.6) -> None:
        self.max_share = max_share

    def reset(self) -> None:
        return None

    def allocate(
        self,
        *,
        gnb_name: str,
        ues_on_gnb: list[dict[str, Any]],
        n_prb_total: int,
    ) -> dict[str, int]:
        if not ues_on_gnb:
            return {}
        sorted_ues = sorted(ues_on_gnb, key=lambda u: -u["sinr_db"])
        rb_alloc: dict[str, int] = {}
        remaining = n_prb_total
        for i, ue in enumerate(sorted_ues):
            if i == 0:
                share = int(n_prb_total * self.max_share)
            else:
                share = max(1, remaining // (len(sorted_ues) - i))
            share = min(share, remaining)
            rb_alloc[ue["id"]] = share
            remaining -= share
            if remaining <= 0:
                break
        return rb_alloc
