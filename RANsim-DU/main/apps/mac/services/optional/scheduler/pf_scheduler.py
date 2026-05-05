"""Proportional Fair scheduler — 對齊 OAI `pf_dl()` (gNB_scheduler_dlsch.c)。

PF_metric(u) = inst_rate(u) / avg_rate(u)
PRB 按 PF_metric 比例分,avg_rate 用 IIR filter (alpha=0.05) 更新。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from main.apps.mac.services.optional.link_adaptation.mcs_table import (
    mcs_to_throughput_mbps,
    sinr_to_mcs,
)
from main.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class _UeSchedState:
    avg_rate_mbps: float = 1.0


class PfScheduler:
    """Proportional Fair scheduler — per-gNB per-tick PRB 分配。"""

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha
        self.ue_state: dict[str, _UeSchedState] = {}

    def reset(self) -> None:
        self.ue_state.clear()

    def allocate(
        self,
        *,
        gnb_name: str,
        ues_on_gnb: list[dict[str, Any]],
        n_prb_total: int,
    ) -> dict[str, int]:
        if not ues_on_gnb:
            return {}

        inst_rates: dict[str, float] = {}
        for ue in ues_on_gnb:
            mcs, bps_re = sinr_to_mcs(ue["sinr_db"])
            inst_rates[ue["id"]] = mcs_to_throughput_mbps(
                mcs=mcs, bps_re=bps_re, n_rb=n_prb_total,
            )

        pf_weights: dict[str, float] = {}
        for ue in ues_on_gnb:
            uid = ue["id"]
            state = self.ue_state.setdefault(uid, _UeSchedState())
            pf_weights[uid] = inst_rates[uid] / max(state.avg_rate_mbps, 1.0)

        total_pf = sum(pf_weights.values())
        if total_pf <= 0:
            share = n_prb_total // len(ues_on_gnb)
            rb_alloc = {ue["id"]: share for ue in ues_on_gnb}
        else:
            rb_alloc = {
                uid: max(1, int(n_prb_total * pf / total_pf))
                for uid, pf in pf_weights.items()
            }
            total_alloc = sum(rb_alloc.values())
            if total_alloc > n_prb_total:
                diff = total_alloc - n_prb_total
                sorted_uids = sorted(rb_alloc, key=lambda u: -rb_alloc[u])
                for uid in sorted_uids:
                    if diff <= 0:
                        break
                    cut = min(diff, rb_alloc[uid] - 1)
                    rb_alloc[uid] -= cut
                    diff -= cut

        for ue in ues_on_gnb:
            uid = ue["id"]
            actual_rate = inst_rates[uid] * rb_alloc[uid] / n_prb_total
            state = self.ue_state[uid]
            state.avg_rate_mbps = (1 - self.alpha) * state.avg_rate_mbps + self.alpha * actual_rate

        logger.debug(
            "PF alloc on %s: %s",
            gnb_name,
            {uid: f"{rb}/{n_prb_total}" for uid, rb in rb_alloc.items()},
        )
        return rb_alloc
