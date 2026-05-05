"""PmAggregatorService — 累積 per-gNB 的 PHY/MAC 計數器。

對應 3GPP TS 28.552 5G Performance Measurements 和 E2.md 的 pm 區塊。

**stateful**: 每 tick accumulate_tick() 累加；build_pm() 輸出累積結果。

對齊 OAI 的關鍵計數器：
  - du_CARR.PDSCHMCSDist.BinTable2.BinMCSxx — 每次 DL 配置的 MCS 直方圖
  - du_CARR.PUSCHMCSDist.BinTable1.BinMCSxx — 每次 UL 配置的 MCS 直方圖
  - du_CARR.WBCQIDist.BinCQIx.BinTable2     — UE 回報 CQI 直方圖（我們從 SINR 反推）
  - du_CARR.PRBUsageDLNbr                   — 累積 DL PRB 使用
  - du_CARR.PRBUsageULNbr                   — 累積 UL PRB 使用
  - cu_DRB.PdcpSduVolumeDL_5QI<n>           — DL PDCP byte volume
  - cu_DRB.PdcpSduVolumeUl_5QI<n>           — UL PDCP byte volume
  - cu_gnb.DRB.SdapSduVolumeDL.5QI<n>       — SDAP byte volume（假設 = PDCP）

Source for struct fields: OAI openair2/LAYER2/NR_MAC_gNB/nr_mac_gNB.h:728-742
Source for HARQ rounds[8]: OAI NR_mac_dir_stats_t
"""
from collections import defaultdict
from typing import Any

from main.apps.ran_signal.services.optional.ran_calculation.cqi_table import sinr_to_cqi
from main.utils.logger import get_logger


logger = get_logger(__name__)

MCS_BINS = 32   # MCS 0~31
CQI_BINS = 16   # CQI 0~15


class _GnbAccumulator:
    """單一 gNB 的 state holder。"""

    def __init__(self, name: str) -> None:
        self.name = name
        self.mcs_dl_bins = [0] * MCS_BINS
        self.mcs_ul_bins = [0] * MCS_BINS
        self.cqi_bins = [0] * CQI_BINS
        self.prb_used_dl = 0                # cumulative PRBs
        self.prb_used_ul = 0
        self.pdcp_bytes_dl: dict[int, int] = defaultdict(int)   # per 5QI
        self.pdcp_bytes_ul: dict[int, int] = defaultdict(int)
        self.harq_rounds_dl = [0] * 8       # 對齊 OAI rounds[8]
        self.harq_errors_dl = 0
        self.harq_rounds_ul = [0] * 8
        self.harq_errors_ul = 0
        self.last_sinr_x10_sum = 0          # SINR × 10 累積（對齊 OAI cumul_sinrx10）
        self.num_sinr_meas = 0
        self.last_rsrp_sum = 0              # 對齊 OAI cumul_rsrp
        self.num_rsrp_meas = 0

    def accumulate_ue(
        self,
        *,
        mcs: int,
        cqi: int,
        rb_width: int,
        sinr_db: float,
        rsrp_dbm: float,
        dl_throughput_mbps: int,
        ul_throughput_mbps: int,
        qos_5qi: int,
        tick_ms: int,
    ) -> None:
        # MCS 直方圖
        if 0 <= mcs < MCS_BINS:
            self.mcs_dl_bins[mcs] += 1
            self.mcs_ul_bins[mcs] += 1

        # CQI 直方圖
        if 0 <= cqi < CQI_BINS:
            self.cqi_bins[cqi] += 1

        # PRB 累積（DL 用滿、UL 估 1/5）
        self.prb_used_dl += rb_width
        self.prb_used_ul += rb_width // 5

        # PDCP byte volume = tput_Mbps × tick_s × 125_000 = bytes
        dt_s = tick_ms / 1000.0
        self.pdcp_bytes_dl[qos_5qi] += int(dl_throughput_mbps * 1e6 * dt_s / 8)
        self.pdcp_bytes_ul[qos_5qi] += int(ul_throughput_mbps * 1e6 * dt_s / 8)

        # HARQ 簡化模型：SINR 決定第幾輪解成
        # SINR >= 12 → 全第 1 輪成；[6,12) → 2 成 1 失; [0,6) → 3 成 1 失; <0 → 失敗
        if sinr_db >= 12:
            self.harq_rounds_dl[0] += 1
            self.harq_rounds_ul[0] += 1
        elif sinr_db >= 6:
            self.harq_rounds_dl[1] += 1
            self.harq_rounds_ul[1] += 1
        elif sinr_db >= 0:
            self.harq_rounds_dl[2] += 1
            self.harq_rounds_ul[2] += 1
        else:
            self.harq_errors_dl += 1
            self.harq_errors_ul += 1

        # 累積 SINR / RSRP 估（對齊 OAI cumul_sinrx10 / cumul_rsrp）
        self.last_sinr_x10_sum += int(sinr_db * 10)
        self.num_sinr_meas += 1
        self.last_rsrp_sum += int(rsrp_dbm)
        self.num_rsrp_meas = min(self.num_rsrp_meas + 1, 255)   # OAI 用 uint8


class PmAggregatorService:
    """所有 gNB 共用一個 Aggregator。stateful。"""

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

    def accumulate_tick(
        self,
        *,
        ue_status_list: list[dict[str, Any]],
        timestamp_ms: int,
        tick_ms: int,
    ) -> None:
        """每 tick 呼叫一次，把 UE KPI 累進 gNB 層級。"""
        if self._start_time_ms is None:
            self._start_time_ms = timestamp_ms

        for ue in ue_status_list:
            serving = ue["serving_gnb"]
            acc = self._acc_for(serving)

            sinr = ue["sinr_db"]
            rsrp = ue["rsrp_dbm"]
            cqi = sinr_to_cqi(sinr)
            # 從 throughput 反推 MCS（近似）
            tput = ue["throughput_dl_mbps"]
            if tput > 400: mcs = 27
            elif tput > 300: mcs = 25
            elif tput > 200: mcs = 23
            elif tput > 100: mcs = 20
            elif tput > 50:  mcs = 16
            elif tput > 20:  mcs = 12
            elif tput > 5:   mcs = 6
            else:            mcs = 0

            # ul throughput 缺就估為 DL/5
            ul_tput = max(1, tput // 5)

            acc.accumulate_ue(
                mcs=mcs,
                cqi=cqi,
                rb_width=273,     # 100 MHz 下的 PRB 數；更準的話應讀 gnb bandwidth
                sinr_db=sinr,
                rsrp_dbm=rsrp,
                dl_throughput_mbps=tput,
                ul_throughput_mbps=ul_tput,
                qos_5qi=ue.get("qos_5qi", 9),
                tick_ms=tick_ms,
            )

    def build_pm(
        self,
        *,
        gnbs: list[dict[str, Any]],
        timestamp_ms: int,
        rrc_counters_by_gnb: dict[str, dict[str, int]],
        bbu_status_by_gnb: dict[str, dict[str, float]],
    ) -> dict[str, list[dict[str, Any]]]:
        """輸出 E2.md 格式的 pm 區塊：{"gnb-<pci>": [{...300 fields...}]}"""
        out: dict[str, list[dict[str, Any]]] = {}
        for idx, gnb in enumerate(gnbs):
            name = gnb["name"]
            pci = gnb.get("pci", idx)
            acc = self._acc.get(name, _GnbAccumulator(name))
            rrc = rrc_counters_by_gnb.get(name, {})
            bbu = bbu_status_by_gnb.get(name, {})

            record = self._gnb_to_pm_record(
                gnb=gnb, pci=pci, acc=acc, timestamp_ms=timestamp_ms,
                rrc_counters=rrc, bbu=bbu,
            )
            out[f"gnb-{pci}"] = [record]
        return out

    def _gnb_to_pm_record(
        self,
        *,
        gnb: dict[str, Any],
        pci: int,
        acc: _GnbAccumulator,
        timestamp_ms: int,
        rrc_counters: dict[str, int],
        bbu: dict[str, float],
    ) -> dict[str, Any]:
        """產生單一 gNB 的 pm record（對齊 E2.md 欄位名稱）。"""
        from datetime import datetime, timezone
        ts_dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        ts_start = (ts_dt).strftime("%Y%m%d.%H%M+0000")
        ts_end = ts_dt.strftime("%H%M+0000")

        record: dict[str, Any] = {
            # Identity
            "cell_id": str(gnb.get("cell_id", f"cell_{pci}")),

            # Timestamps
            "cu_timestamp_start": ts_start,
            "cu_timestamp_end": ts_end,
            "cu_filename": f"A{ts_start}-{ts_end}_{pci}-cu.xml",
            "du_timestamp_start": ts_start,
            "du_timestamp_end": ts_end,
            "du_filename": f"A{ts_start}-{ts_end}_{pci}-du.xml",

            # CU capability
            "cu_CU_Capability": "1",
        }

        # ─── RRC counters (from RrcEventTracker) ───
        record.update({
            "cu_RRC.ConnEstabAtt.sum": str(rrc_counters.get("RRC.ConnEstabAtt.sum", 0)),
            "cu_RRC.ConnEstabAtt.mo-Data": str(rrc_counters.get("RRC.ConnEstabAtt.mo-Data", 0)),
            "cu_RRC.ConnEstabAtt.mo-Signalling": "0",
            "cu_RRC.ConnEstabSucc.sum": str(rrc_counters.get("RRC.ConnEstabSucc.sum", 0)),
            "cu_RRC.ConnEstabSucc.mo-Data": str(rrc_counters.get("RRC.ConnEstabSucc.mo-Data", 0)),
            "cu_RRC.ConnEstabSucc.mo-Signalling": "0",
            "cu_RRC.ConnEstabSucc.emergency": "0",
            "cu_RRC.ConnMax": str(rrc_counters.get("RRC.ConnMax", 0)),
            "cu_RRC.ConnMean": str(rrc_counters.get("RRC.ConnMean", 0)),
            "cu_RRC.ConnReEstabSetup.sum": "0",
            "cu_RRC.ReEstabAtt": "0",
            "cu_RRC.ReEstabAtt.otherFailure": "0",
            "cu_RRC.ReEstabSuccWithUeContext.sum": "0",
            "cu_RRC.ReEstabSuccWithUeContext.otherFailure": "0",
            "cu_RRC.ReEstabSuccWithoutUeContext.sum": "0",
            "cu_RRC.ReEstabSuccWithoutUeContext.otherFailure": "0",
        })

        # Handover & Mobility
        record.update({
            "cu_MM.HoExeIntraFreqReq": str(rrc_counters.get("MM.HoExeIntraFreqReq", 0)),
            "cu_MM.HoExeIntraFreqSucc": str(rrc_counters.get("MM.HoExeIntraFreqSucc", 0)),
            "cu_MM.HoExeIntraReq": str(rrc_counters.get("MM.HoExeIntraReq", 0)),
            "cu_MM.HoExeIntraSucc": str(rrc_counters.get("MM.HoExeIntraSucc", 0)),
            "cu_MM.HoPrepIntraReq": str(rrc_counters.get("MM.HoPrepIntraReq", 0)),
            "cu_MM.HoPrepIntraSucc": str(rrc_counters.get("MM.HoPrepIntraSucc", 0)),
            "cu_gnb.MR.Event.A3": str(rrc_counters.get("gnb.MR.Event.A3", 0)),
        })

        # UE Context
        record.update({
            "cu_UECNTX.ConnEstabAtt.sum": str(rrc_counters.get("RRC.ConnEstabAtt.sum", 0)),
            "cu_UECNTX.ConnEstabAtt.mo-Data": str(rrc_counters.get("RRC.ConnEstabAtt.mo-Data", 0)),
            "cu_UECNTX.ConnEstabAtt.mo-Signalling": "0",
            "cu_UECNTX.ConnEstabSucc.sum": str(rrc_counters.get("RRC.ConnEstabSucc.sum", 0)),
            "cu_UECNTX.ConnEstabSucc.mo-Data": str(rrc_counters.get("RRC.ConnEstabSucc.mo-Data", 0)),
            "cu_UECNTX.ConnEstabSucc.mo-Signalling": "0",
            "cu_UECNTX.Release.5GCinit.NASCause": "0",
            "cu_UECNTX.Release.5GCinit.RNCause": "0",
            "cu_UECNTX.Release.5GCinit.sum": str(rrc_counters.get("UECNTX.Release.5GCinit.sum", 0)),
            "cu_gnb.UECNTX.Release.gNBinit.RNCause": "0",
            "cu_gnb.UECNTX.Release.gNBinit.sum": "0",
        })

        # PDU Session / SM
        record.update({
            "cu_SM.PDUSessionSetupReq": str(rrc_counters.get("SM.PDUSessionSetupReq", 0)),
            "cu_SM.PDUSessionSetupSucc": str(rrc_counters.get("SM.PDUSessionSetupSucc", 0)),
            "cu_gnb.SM.PDUSessionRelease.Att": "0",
            "cu_gnb.SM.PDUSessionRelease.Succ": "0",
        })

        # DRB
        record.update({
            "cu_DRB.EstabAtt.5QI.sum": str(rrc_counters.get("DRB.EstabAtt.sum", 0)),
            "cu_DRB.EstabAtt.5QI9": str(rrc_counters.get("DRB.EstabAtt.5QI9", 0)),
            "cu_DRB.EstabSucc.5QI.sum": str(rrc_counters.get("DRB.EstabSucc.sum", 0)),
            "cu_DRB.EstabSucc.5QI9": str(rrc_counters.get("DRB.EstabSucc.5QI9", 0)),
            "cu_DRB.InitialEstabAtt.5QI.sum": str(rrc_counters.get("DRB.EstabAtt.sum", 0)),
            "cu_DRB.InitialEstabAtt.5QI1": "0",
            "cu_DRB.InitialEstabSucc.5QI.sum": str(rrc_counters.get("DRB.EstabSucc.sum", 0)),
            "cu_DRB.InitialEstabSucc.5QI9": str(rrc_counters.get("DRB.EstabSucc.5QI9", 0)),
            "cu_DRB.PdcpPacketDiscardDL.5QI9": "0",
            "cu_DRB.PdcpReordDelayUl": "3",
            "cu_DRB.RelActNbr.5QI.sum": "0",
            "cu_DRB.RelActNbr.5QI9": "0",
            "cu_DRB.SessionTime.5QI.sum": "0",
            "cu_DRB.SessionTime.5QI9": "0",
        })

        # PDCP / SDAP Volume — 多 QoS 分桶
        # 5QI1 = VoNR 語音；5QI4 = 影片；5QI9 = best-effort 資料
        for qos in (1, 4, 9):
            key_suffix = f"5QI{qos}"
            record[f"cu_DRB.PdcpSduVolumeDL_{key_suffix}"] = str(acc.pdcp_bytes_dl.get(qos, 0))
            record[f"cu_DRB.PdcpSduVolumeUl_{key_suffix}"] = str(acc.pdcp_bytes_ul.get(qos, 0))
            record[f"cu_gnb.DRB.SdapSduVolumeDL.{key_suffix}"] = str(acc.pdcp_bytes_dl.get(qos, 0))
            record[f"cu_gnb.DRB.SdapSduVolumeUl.{key_suffix}"] = str(acc.pdcp_bytes_ul.get(qos, 0))

        # QoS Flow（stub）
        record.update({
            "cu_QF.EstabAttNbr.5QI.sum": "0",
            "cu_QF.EstabAttNbr.5QI9": "0",
            "cu_QF.EstabSuccNbr.5QI.sum": "0",
            "cu_QF.EstabSuccNbr.5QI9": "0",
            "cu_QF.InitialEstabAttNbr.5QI.sum": "0",
            "cu_QF.InitialEstabAttNbr.5QI9": "0",
            "cu_QF.InitialEstabSuccNbr.5QI.sum": "0",
            "cu_QF.InitialEstabSuccNbr.5QI9": "0",
            "cu_QF.RelActNbr.Qos.sum": "0",
            "cu_QF.RelActNbr.Qos9": "0",
            "cu_QF.ReleaseAttNbr.5QI.sum": "0",
            "cu_QF.ReleaseAttNbr.5QI9": "0",
        })

        # RRC Setup / Reconfig timings（stub — 需要真信令）
        record.update({
            "cu_gnb.RRC.ConnEstabSetup.emergency": "0",
            "cu_gnb.RRC.ConnEstabSetup.mo-Data": "0",
            "cu_gnb.RRC.ConnEstabSetup.mo-Signalling": "0",
            "cu_gnb.RRC.ConnEstabSetup.sum": str(rrc_counters.get("RRC.ConnEstabSucc.sum", 0)),
            "cu_gnb.RRC.ConnReConfigAtt": "0",
            "cu_gnb.RRC.ConnReConfigSucc": "0",
            "cu_gnb.RRC.ConnReEstab.ReEstab.otherFailure": "0",
            "cu_gnb.RRC.ConnReEstab.ReEstab.sum": "0",
            "cu_gnb.RRC.ConnReEstabSetup.otherFailure": "0",
            "cu_gnb.RRC.ConnRelease.Other": "0",
            "cu_gnb.RRC.ConnRelease.sum": "0",
            "cu_gnb.RRC.SigTimeReEstab.Avg": "0",
            "cu_gnb.RRC.SigTimeReEstab.Max": "0",
            "cu_gnb.RRC.SigTimeReconfig.Avg": "0",
            "cu_gnb.RRC.SigTimeReconfig.Max": "0",
            "cu_gnb.RRC.SigTimeSetup.Avg": "0",
            "cu_gnb.RRC.SigTimeSetup.Max": "0",
        })

        # ─── DU stats ───

        # PEE (Power, Energy, Environment) — 從 bbu_status 借
        record.update({
            "du_169:PEE.AvgTemperature": str(bbu.get("cpu_temp", 0.0)),
            "du_170:PEE.MinTemperature": str(max(0.0, bbu.get("cpu_temp", 0.0) - 5.0)),
            "du_171:PEE.MaxTemperature": str(bbu.get("cpu_temp", 0.0) + 5.0),
        })

        # PDSCH MCS 分佈（★ 我們實際累積）
        for i, count in enumerate(acc.mcs_dl_bins):
            record[f"du_CARR.PDSCHMCSDist.BinTable2.BinMCS{i}"] = str(count)

        # PUSCH MCS 分佈
        for i, count in enumerate(acc.mcs_ul_bins):
            record[f"du_CARR.PUSCHMCSDist.BinTable1.BinMCS{i}"] = str(count)

        # CQI 分佈
        for i, count in enumerate(acc.cqi_bins):
            record[f"du_CARR.WBCQIDist.BinCQI{i}.BinTable2"] = str(count)

        # PRB 使用
        record.update({
            "du_CARR.PRBUsageDLNbr": str(acc.prb_used_dl),
            "du_CARR.PRBUsageULNbr": str(acc.prb_used_ul),
        })

        # Air Interface Delay (stub — 需 HARQ 實況)
        record.update({
            "du_DRB.AirIfDelayDlAvg.5QI1": "0",
            "du_DRB.AirIfDelayDlAvg.5QI9": "0",
            "du_DRB.AirIfDelayUlAvg.5QI1": "0",
            "du_DRB.AirIfDelayUlAvg.5QI9": "0",
        })

        return record
