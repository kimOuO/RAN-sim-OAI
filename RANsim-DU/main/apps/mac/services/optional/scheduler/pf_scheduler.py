"""Proportional Fair scheduler — 對齊 OAI `pf_dl()` (gNB_scheduler_dlsch.c)。

PF_metric(u) = inst_rate(u) / avg_rate(u)
PRB 按 PF_metric 比例分,avg_rate 用 IIR filter (alpha=0.05) 更新。

AL1 — per-UE PRB cap by demand (對齊 OAI dlsch_scheduler):
  prb_needed = ceil(buffer_bytes * 8 / (bits_per_PRB_per_tick))
  Pass 1: rb_alloc = min(prb_fair_share, prb_needed)
  Pass 2: leftover PRB 給仍有 buffer 但分得不夠的 UE (second-pass greedy refill)
若 ue dict 沒 buffer_occupancy 欄位, 視為 demand 無限 (向後相容 / fallback).
"""
from __future__ import annotations

import math
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
        tick_ms: int = 500,
    ) -> dict[str, int]:
        if not ues_on_gnb:
            return {}

        # ── 1. Per-UE inst_rate + prb_needed (demand cap) ──
        tick_s = tick_ms / 1000.0
        inst_rates: dict[str, float] = {}
        prb_needed: dict[str, int] = {}
        for ue in ues_on_gnb:
            uid = ue["id"]
            mcs, bps_re = sinr_to_mcs(ue["sinr_db"])
            inst_rates[uid] = mcs_to_throughput_mbps(
                mcs=mcs, bps_re=bps_re, n_rb=n_prb_total,
            )
            buf_bytes = ue.get("buffer_occupancy")
            if buf_bytes is None:
                # 沒 buffer info — 視為無限 demand (向後相容老 caller)
                prb_needed[uid] = n_prb_total
            elif buf_bytes <= 0:
                # buffer 空 — 不需 PRB. tick_runner 已先 filter, 防禦性處理.
                prb_needed[uid] = 1
            elif bps_re <= 0:
                # MCS 0 (SINR < -6 dB) — bps_re=0, 給 1 PRB 試送
                prb_needed[uid] = 1
            else:
                # 直接 float 計算, 不走 mcs_to_throughput_mbps() 避免 int() 截 0
                # 對齊原公式: re_per_slot = 1 PRB × 12 subcarrier × 12 symbol = 144
                # bits/sec = re_per_slot × bps_re × slots_per_sec × overhead
                # 常數見 mcs_table.mcs_to_throughput_mbps: slots_per_sec=2000, overhead=0.85
                bits_per_prb_per_sec = 144.0 * bps_re * 2000.0 * 0.85
                bytes_per_prb = bits_per_prb_per_sec * tick_s / 8.0
                prb_needed[uid] = max(1, math.ceil(buf_bytes / bytes_per_prb))

        # ── 2. PF metric weights ──
        pf_weights: dict[str, float] = {}
        for ue in ues_on_gnb:
            uid = ue["id"]
            state = self.ue_state.setdefault(uid, _UeSchedState())
            pf_weights[uid] = inst_rates[uid] / max(state.avg_rate_mbps, 1.0)

        # ── 3. Pass 1: fair share with demand cap ──
        total_pf = sum(pf_weights.values())
        rb_alloc: dict[str, int] = {}
        if total_pf <= 0:
            share = max(1, n_prb_total // len(ues_on_gnb))
            for ue in ues_on_gnb:
                uid = ue["id"]
                rb_alloc[uid] = min(share, prb_needed[uid])
        else:
            for ue in ues_on_gnb:
                uid = ue["id"]
                fair = max(1, int(n_prb_total * pf_weights[uid] / total_pf))
                rb_alloc[uid] = min(fair, prb_needed[uid])

        # ── 4. Pass 2: redistribute leftover to UEs still short of need ──
        leftover = n_prb_total - sum(rb_alloc.values())
        if leftover > 0:
            sorted_uids = sorted(pf_weights, key=lambda u: -pf_weights[u])
            for uid in sorted_uids:
                if leftover <= 0:
                    break
                short = prb_needed[uid] - rb_alloc[uid]
                if short > 0:
                    give = min(leftover, short)
                    rb_alloc[uid] += give
                    leftover -= give

        # ── 5. Trim if overshoot (defensive after demand cap) ──
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

        # ── 6. Update avg_rate (IIR filter) ──
        for ue in ues_on_gnb:
            uid = ue["id"]
            actual_rate = inst_rates[uid] * rb_alloc[uid] / n_prb_total
            state = self.ue_state[uid]
            state.avg_rate_mbps = (
                (1 - self.alpha) * state.avg_rate_mbps + self.alpha * actual_rate
            )

        used = sum(rb_alloc.values())
        logger.debug(
            "PF alloc on %s: %s used=%d/%d (leftover=%d)",
            gnb_name,
            {uid: f"{rb}/{n_prb_total}" for uid, rb in rb_alloc.items()},
            used, n_prb_total, n_prb_total - used,
        )
        return rb_alloc
