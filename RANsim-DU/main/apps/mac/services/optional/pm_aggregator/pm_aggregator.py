"""PmAggregator — 累積 per-gNB 的 PHY/MAC 計數器,供 measurement_report 上報。

對齊 3GPP TS 28.552 5G PM。OAI 對應:
  - openair2/LAYER2/NR_MAC_gNB/nr_mac_gNB.h:728-742  (NR_mac_dir_stats_t)
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from main.apps.mac.services.optional.link_adaptation.cqi_table import sinr_to_cqi
from main.utils.logger import get_logger

logger = get_logger(__name__)

MCS_BINS = 32
CQI_BINS = 16


class _GnbAccumulator:
    def __init__(self, name: str) -> None:
        self.name = name
        self.mcs_dl_bins = [0] * MCS_BINS
        self.mcs_ul_bins = [0] * MCS_BINS
        self.cqi_bins = [0] * CQI_BINS
        self.prb_used_dl = 0
        self.prb_used_ul = 0
        self.pdcp_bytes_dl: dict[int, int] = defaultdict(int)
        self.pdcp_bytes_ul: dict[int, int] = defaultdict(int)
        self.harq_rounds_dl = [0] * 8
        self.harq_errors_dl = 0
        self.harq_rounds_ul = [0] * 8
        self.harq_errors_ul = 0
        self.last_sinr_x10_sum = 0
        self.num_sinr_meas = 0
        self.last_rsrp_sum = 0
        self.num_rsrp_meas = 0


class PmAggregatorService:
    """所有 gNB 共用一個 Aggregator,stateful。"""

    def __init__(self) -> None:
        self._acc: dict[str, _GnbAccumulator] = {}
        self._start_time_ms: int | None = None

    def reset(self) -> None:
        self._acc.clear()
        self._start_time_ms = None

    def _acc_for(self, gnb_name: str) -> _GnbAccumulator:
        if gnb_name not in self._acc:
            self._acc[gnb_name] = _GnbAccumulator(gnb_name)
        return self._acc[gnb_name]

    def accumulate_ue(
        self,
        *,
        gnb_name: str,
        mcs_dl: int,
        mcs_ul: int,
        sinr_db: float,
        rsrp_dbm: float,
        prb_dl: int,
        prb_ul: int,
        dl_bytes: int,
        ul_bytes: int,
        qos_5qi: int,
    ) -> None:
        acc = self._acc_for(gnb_name)
        if 0 <= mcs_dl < MCS_BINS:
            acc.mcs_dl_bins[mcs_dl] += 1
        if 0 <= mcs_ul < MCS_BINS:
            acc.mcs_ul_bins[mcs_ul] += 1
        cqi = sinr_to_cqi(sinr_db)
        if 0 <= cqi < CQI_BINS:
            acc.cqi_bins[cqi] += 1
        acc.prb_used_dl += prb_dl
        acc.prb_used_ul += prb_ul
        acc.pdcp_bytes_dl[qos_5qi] += dl_bytes
        acc.pdcp_bytes_ul[qos_5qi] += ul_bytes
        if sinr_db >= 12:
            acc.harq_rounds_dl[0] += 1
            acc.harq_rounds_ul[0] += 1
        elif sinr_db >= 6:
            acc.harq_rounds_dl[1] += 1
            acc.harq_rounds_ul[1] += 1
        elif sinr_db >= 0:
            acc.harq_rounds_dl[2] += 1
            acc.harq_rounds_ul[2] += 1
        else:
            acc.harq_errors_dl += 1
            acc.harq_errors_ul += 1
        acc.last_sinr_x10_sum += int(sinr_db * 10)
        acc.num_sinr_meas += 1
        acc.last_rsrp_sum += int(rsrp_dbm)
        acc.num_rsrp_meas = min(acc.num_rsrp_meas + 1, 255)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for name, acc in self._acc.items():
            avg_sinr = acc.last_sinr_x10_sum / 10.0 / max(acc.num_sinr_meas, 1)
            avg_rsrp = acc.last_rsrp_sum / max(acc.num_rsrp_meas, 1)
            out[name] = {
                "mcs_dl_bins": acc.mcs_dl_bins,
                "mcs_ul_bins": acc.mcs_ul_bins,
                "cqi_bins": acc.cqi_bins,
                "prb_used_dl": acc.prb_used_dl,
                "prb_used_ul": acc.prb_used_ul,
                "pdcp_bytes_dl": dict(acc.pdcp_bytes_dl),
                "pdcp_bytes_ul": dict(acc.pdcp_bytes_ul),
                "harq_rounds_dl": acc.harq_rounds_dl,
                "harq_errors_dl": acc.harq_errors_dl,
                "harq_rounds_ul": acc.harq_rounds_ul,
                "harq_errors_ul": acc.harq_errors_ul,
                "avg_sinr_db": avg_sinr,
                "avg_rsrp_dbm": avg_rsrp,
            }
        return out


_singleton: PmAggregatorService | None = None


def get_pm_aggregator() -> PmAggregatorService:
    global _singleton
    if _singleton is None:
        _singleton = PmAggregatorService()
    return _singleton
