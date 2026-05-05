"""Proportional Fair (PF) scheduler — 多 UE 共享單 gNB 的 PRB 資源。

對齊 OAI `pf_dl()` in openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_dlsch.c：
  PF_metric(u) = inst_rate(u) / avg_rate(u)
  PRB 按 PF_metric 比例分
  avg_rate 用 IIR filter (alpha=0.05) 更新

stateful: 每 UE 維護歷史平均速率跨 tick。
"""
from dataclasses import dataclass
from typing import Any

from main.apps.ran_signal.services.optional.ran_calculation.mcs_table import (
    mcs_to_throughput_mbps,
    sinr_to_mcs,
)
from main.utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class _UeSchedState:
    avg_rate_mbps: float = 1.0     # 歷史平均 throughput（初始 1 Mbps 避免除零）


class PfScheduler:
    """Proportional Fair scheduler — per-gNB per-tick PRB 分配。"""

    def __init__(self, alpha: float = 0.05):
        """alpha: IIR filter 權重，越小越平滑（OAI 預設 ~0.01~0.05）。"""
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
        """對單一 gNB 上的 UE 分 PRB。

        Args:
            gnb_name: 該 gNB 名稱（僅 log 用）
            ues_on_gnb: list of dict with keys {id, sinr_db}
            n_prb_total: 該 gNB 的 PRB 總數（ex: 100 MHz → 273）

        Returns:
            {ue_id: allocated_rb_width}
        """
        if not ues_on_gnb:
            return {}

        # Step 1: 瞬時可達速率（若該 UE 獨享全部 PRB）
        inst_rates: dict[str, float] = {}
        for ue in ues_on_gnb:
            mcs, bps_re = sinr_to_mcs(ue["sinr_db"])
            inst_rates[ue["id"]] = mcs_to_throughput_mbps(
                mcs=mcs, bps_re=bps_re, n_rb=n_prb_total,
            )

        # Step 2: PF metric = 瞬時 / 歷史平均
        pf_weights: dict[str, float] = {}
        for ue in ues_on_gnb:
            uid = ue["id"]
            state = self.ue_state.setdefault(uid, _UeSchedState())
            pf_weights[uid] = inst_rates[uid] / max(state.avg_rate_mbps, 1.0)

        # Step 3: 按 PF 權重分 PRB（正規化 + 整數化）
        total_pf = sum(pf_weights.values())
        if total_pf <= 0:
            # fallback：平均分
            share = n_prb_total // len(ues_on_gnb)
            rb_alloc = {ue["id"]: share for ue in ues_on_gnb}
        else:
            rb_alloc = {
                uid: max(1, int(n_prb_total * pf / total_pf))
                for uid, pf in pf_weights.items()
            }
            # 修正 rounding 誤差：總和不超過 n_prb_total
            total_alloc = sum(rb_alloc.values())
            if total_alloc > n_prb_total:
                # 按比例回扣最大的幾個
                diff = total_alloc - n_prb_total
                sorted_uids = sorted(rb_alloc, key=lambda u: -rb_alloc[u])
                for uid in sorted_uids:
                    if diff <= 0:
                        break
                    cut = min(diff, rb_alloc[uid] - 1)
                    rb_alloc[uid] -= cut
                    diff -= cut

        # Step 4: 更新歷史平均（IIR filter）— 用實際分到的 PRB 計算實際速率
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
