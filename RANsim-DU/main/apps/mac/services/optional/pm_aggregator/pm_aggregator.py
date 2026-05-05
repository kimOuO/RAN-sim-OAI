"""PmAggregator — 累積 per-gNB 的 PHY/MAC 計數器 + per-UE window,供 measurement_report 上報。

對齊 3GPP TS 28.552 5G PM。OAI 對應:
  - openair2/LAYER2/NR_MAC_gNB/nr_mac_gNB.h:728-742  (NR_mac_dir_stats_t)

兩層累積:
  - per-gNB:整段 session 累進(MCS/CQI bins、PRB total、bytes、HARQ rounds...)
  - per-UE window:report 之間滾動;每次 flush_ue_report() 取平均/總和並 reset
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from main.apps.mac.services.optional.link_adaptation.cqi_table import sinr_to_cqi
from main.utils.logger import get_logger

logger = get_logger(__name__)

MCS_BINS = 32
CQI_BINS = 16


@dataclass
class _UeWindowAccumulator:
    """每個 UE 在 report 之間的 rolling stats。flush 後 reset。"""
    serving_cell: str = ""
    samples: int = 0
    sinr_db_sum: float = 0.0
    rsrp_dbm_sum: float = 0.0
    mcs_dl_sum: int = 0
    mcs_ul_sum: int = 0
    rank_sum: int = 0
    prb_dl_sum: int = 0
    prb_ul_sum: int = 0
    dl_bytes_sum: int = 0
    ul_bytes_sum: int = 0
    last_qos_5qi: int = 9

    def add(
        self,
        *,
        serving_cell: str,
        sinr_db: float,
        rsrp_dbm: float,
        mcs_dl: int,
        mcs_ul: int,
        rank: int,
        prb_dl: int,
        prb_ul: int,
        dl_bytes: int,
        ul_bytes: int,
        qos_5qi: int,
    ) -> None:
        self.serving_cell = serving_cell
        self.samples += 1
        self.sinr_db_sum += sinr_db
        self.rsrp_dbm_sum += rsrp_dbm
        self.mcs_dl_sum += mcs_dl
        self.mcs_ul_sum += mcs_ul
        self.rank_sum += rank
        self.prb_dl_sum += prb_dl
        self.prb_ul_sum += prb_ul
        self.dl_bytes_sum += dl_bytes
        self.ul_bytes_sum += ul_bytes
        self.last_qos_5qi = qos_5qi

    def flush(self, window_seconds: float) -> dict[str, Any]:
        """回傳這個 window 的 averaged report,並 reset 累計欄位。"""
        n = max(self.samples, 1)
        report = {
            "serving_cell": self.serving_cell,
            "samples": self.samples,
            "avg_sinr_db": self.sinr_db_sum / n,
            "avg_rsrp_dbm": self.rsrp_dbm_sum / n,
            "avg_mcs_dl": int(round(self.mcs_dl_sum / n)),
            "avg_mcs_ul": int(round(self.mcs_ul_sum / n)),
            "avg_rank": max(1, int(round(self.rank_sum / n))),
            "avg_prb_dl": int(round(self.prb_dl_sum / n)),
            "avg_prb_ul": int(round(self.prb_ul_sum / n)),
            "throughput_dl_mbps": (self.dl_bytes_sum * 8) / max(window_seconds, 1e-3) / 1e6,
            "throughput_ul_mbps": (self.ul_bytes_sum * 8) / max(window_seconds, 1e-3) / 1e6,
            "qos_5qi": self.last_qos_5qi,
        }
        # reset
        self.samples = 0
        self.sinr_db_sum = 0.0
        self.rsrp_dbm_sum = 0.0
        self.mcs_dl_sum = 0
        self.mcs_ul_sum = 0
        self.rank_sum = 0
        self.prb_dl_sum = 0
        self.prb_ul_sum = 0
        self.dl_bytes_sum = 0
        self.ul_bytes_sum = 0
        return report


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
        self._ue_window: dict[str, _UeWindowAccumulator] = {}
        self._start_time_ms: int | None = None

    def reset(self) -> None:
        self._acc.clear()
        self._ue_window.clear()
        self._start_time_ms = None

    def _acc_for(self, gnb_name: str) -> _GnbAccumulator:
        if gnb_name not in self._acc:
            self._acc[gnb_name] = _GnbAccumulator(gnb_name)
        return self._acc[gnb_name]

    def _ue_acc_for(self, ue_id: str) -> _UeWindowAccumulator:
        acc = self._ue_window.get(ue_id)
        if acc is None:
            acc = _UeWindowAccumulator()
            self._ue_window[ue_id] = acc
        return acc

    def accumulate_ue(
        self,
        *,
        gnb_name: str,
        ue_id: str | None = None,
        mcs_dl: int,
        mcs_ul: int,
        sinr_db: float,
        rsrp_dbm: float,
        prb_dl: int,
        prb_ul: int,
        dl_bytes: int,
        ul_bytes: int,
        qos_5qi: int,
        rank: int = 1,
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

        if ue_id:
            self._ue_acc_for(ue_id).add(
                serving_cell=gnb_name,
                sinr_db=sinr_db,
                rsrp_dbm=rsrp_dbm,
                mcs_dl=mcs_dl,
                mcs_ul=mcs_ul,
                rank=rank,
                prb_dl=prb_dl,
                prb_ul=prb_ul,
                dl_bytes=dl_bytes,
                ul_bytes=ul_bytes,
                qos_5qi=qos_5qi,
            )

    def flush_ue_report(self, ue_id: str, window_seconds: float) -> dict[str, Any] | None:
        """取出 UE 在 window 內的累積報告並 reset。沒資料回 None。"""
        acc = self._ue_window.get(ue_id)
        if acc is None or acc.samples == 0:
            return None
        return acc.flush(window_seconds)

    def remove_ue(self, ue_id: str) -> None:
        self._ue_window.pop(ue_id, None)

    def active_ue_ids(self) -> list[str]:
        return [uid for uid, acc in self._ue_window.items() if acc.samples > 0]

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
