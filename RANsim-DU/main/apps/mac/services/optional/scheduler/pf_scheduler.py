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
    TDD_DL_SLOT_RATIO,
    mcs_to_throughput_mbps,
    sinr_to_mcs,
)
from main.utils.env_loader import get_bool, get_int
from main.utils.logger import get_logger

# slot 引擎接管:scheduler 改用「操作點 MCS」算 PRB 需求(取代樂觀 sinr_to_mcs)+ 低載地板,
# 讓 PRB%/throughput/delay 三者用同一套真實 MCS,對齊 OAI。off 時走舊樂觀路徑。
_SCHED_MCS_CONSISTENT = get_bool("SLOT_ENGINE_TAKEOVER", False)
_OP_PRB_FLOOR = get_int("SLOT_OP_PRB_FLOOR", 12)
# retx-aware demand:scheduler 算 prb_needed 時把 slot 引擎實際在用的 BLER 算進去
# (容量 ×(1-BLER)= 真正送得出去的量),避免「以為 100% 成功」少開 PRB → backlog 積爆。
# 對齊 OAI outer-loop link adaptation / 有效 TBS 為重傳預留資源。off 走舊樂觀路徑。
_SCHED_RETX_AWARE = get_bool("SLOT_SCHED_RETX_AWARE", True)

logger = get_logger(__name__)


# OAI PF scheduler 強制最小 5 PRB 分配 — 對齊 OAI gNB_scheduler_dlsch.c:753:
#   `const int min_rbSize = 5;`
# 即使 UE 只需 1 PRB 容量,OAI 也分 5 PRB(避免 DCI 浪費 + 留 retx margin)。
# DT 加這個下限後 prb_pct 從 ~0.6% 拉到 ~4.7%,接近 OAI 10.67%(剩 ~6% 為 OAI
# 的 retx + SDU 多 PDU 切分,DT 沒模擬)。
# 詳見 docs/test_records/oai_prb_calc_evidence_2026-05-23.md
MIN_PRB = 5


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
            retx_eff = 1.0   # 1 = 不打折(舊行為)
            if _SCHED_MCS_CONSISTENT:
                # 操作點 MCS:挑首傳 BLER≤10% 的最高 MCS(跟 slot 引擎同源,真實鏈路可達)
                from main.apps.mac.services.optional.slot_engine.slot_loop import (
                    _eff_for_mcs, _mcs_at_op_point,
                )
                mcs = _mcs_at_op_point(ue["sinr_db"], 0.1)
                bps_re = _eff_for_mcs(mcs)
                if _SCHED_RETX_AWARE:
                    # 用 slot 引擎同一個 BLER:期望需傳 1/(1-BLER) 次才成功 → 容量 ×(1-BLER)
                    from main.apps.mac.services.optional.slot_engine.bler_table import bler
                    b = bler(mcs, ue["sinr_db"])
                    retx_eff = max(0.05, 1.0 - float(b))
            else:
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
                # bits/sec = re_per_slot × bps_re × slots_per_sec × overhead × tdd_dl_ratio
                # 常數見 mcs_table.mcs_to_throughput_mbps: slots_per_sec=2000, overhead=0.80
                bits_per_prb_per_sec = 144.0 * bps_re * 2000.0 * 0.80 * TDD_DL_SLOT_RATIO
                bytes_per_prb = bits_per_prb_per_sec * tick_s / 8.0
                # retx-aware:扣掉 BLER,為重傳預留 PRB(retx_eff=1 時 = 舊行為)
                prb_needed[uid] = max(1, math.ceil(buf_bytes / (bytes_per_prb * retx_eff)))
            # slot 引擎接管:有 buffer 的 UE 套低載地板(不被餓死,= OAI 空 cell 大方給)
            if _SCHED_MCS_CONSISTENT and (buf_bytes or 0) > 0:
                prb_needed[uid] = min(n_prb_total, max(prb_needed[uid], _OP_PRB_FLOOR))

        # ── 2. PF metric weights ──
        pf_weights: dict[str, float] = {}
        for ue in ues_on_gnb:
            uid = ue["id"]
            state = self.ue_state.setdefault(uid, _UeSchedState())
            pf_weights[uid] = inst_rates[uid] / max(state.avg_rate_mbps, 1.0)

        # ── 3. Pass 1: fair share with demand cap ──
        # P1.14 (2026-05-25): 改 demand-based MIN_PRB —
        # 舊行為 (P1.9): 有 BO UE 強分 MIN_PRB=5 即使 demand 只有 1 PRB → low-rate phase
        # (normal-2 16 kbps / normal-3 5 kbps) 被分過頭 PRB,PRB% 報出來 11% 對 OAI 0.26-0.89%
        # 過高 12-43×。
        # 新行為: floor = min(MIN_PRB, prb_needed) — UE 只拿真實 demand 對應 PRB,
        # demand >= 5 才拉到 5。對齊 OAI dlsch_scheduler:demand-driven 分 PRB,不浪費。
        # 預期: normal-2/3 PRB% 從 11% 降到 ~1%,normal-1/im 不變 (demand 已 >= 5)。
        total_pf = sum(pf_weights.values())
        rb_alloc: dict[str, int] = {}

        def _floor_for(uid: str, ue: dict[str, Any]) -> int:
            buf = ue.get("buffer_occupancy")
            # buffer empty / measurement-only UE: 維持 1 PRB(對齊 OAI 不浪費 PRB 給 idle UE)
            if buf is None or buf <= 0:
                return 1
            # P1.14: floor cap by demand — low-rate UE 不再被強拉到 5
            return min(MIN_PRB, prb_needed[uid])

        if total_pf <= 0:
            share = max(1, n_prb_total // len(ues_on_gnb))
            for ue in ues_on_gnb:
                uid = ue["id"]
                floor = _floor_for(uid, ue)
                rb_alloc[uid] = min(max(share, floor), prb_needed[uid] if floor == 1 else max(prb_needed[uid], floor))
        else:
            for ue in ues_on_gnb:
                uid = ue["id"]
                floor = _floor_for(uid, ue)
                fair = max(1, int(n_prb_total * pf_weights[uid] / total_pf))
                # OAI: nr_find_nb_rb 強制 ≥ min_rbSize。即使 fair=1 也拉到 MIN_PRB,
                # 但不超過 n_prb_total(防超 BW)。對 idle UE (floor=1) 退回原本 demand cap。
                if floor == 1:
                    rb_alloc[uid] = min(fair, prb_needed[uid])
                else:
                    target = max(fair, floor)
                    rb_alloc[uid] = min(target, n_prb_total, max(prb_needed[uid], floor))

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
