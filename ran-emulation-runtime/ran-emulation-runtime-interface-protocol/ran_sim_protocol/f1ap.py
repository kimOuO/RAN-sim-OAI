"""F1AP message types — CU ↔ DU 介面。

對應 OAI: openair2/F1AP/, 3GPP TS 38.473
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ran_sim_protocol.common import CellConfig, DrbConfig, NeighborMeas


@dataclass
class F1Setup:
    """DU 啟動時送給 CU。"""
    gnb_du_id: int
    served_cells: list[CellConfig] = field(default_factory=list)


@dataclass
class F1SetupResponse:
    """CU 回 DU 的 ACK。"""
    transaction_id: int
    accepted: bool = True


@dataclass
class UeContextSetup:
    """CU 對 DU 說「為這個 UE 配資源」（CU → DU）。"""
    ue_id: str
    drbs: list[DrbConfig] = field(default_factory=list)
    rrc_message_b64: str = ""  # base64 of opaque RRC container


@dataclass
class UeContextSetupResponse:
    """DU 回 CU 的 ACK，帶資源分配結果。"""
    ue_id: str
    success: bool
    drb_setup_list: list[int] = field(default_factory=list)


@dataclass
class UeContextRelease:
    """CU → DU：釋放 UE。"""
    ue_id: str
    cause: str = "normal"


@dataclass
class DlRrcMessageTransfer:
    """CU → DU → UE 的 RRC 訊息（opaque container）。"""
    ue_id: str
    rrc_msg_b64: str


@dataclass
class UlRrcMessageTransfer:
    """UE → DU → CU。"""
    ue_id: str
    rrc_msg_b64: str


@dataclass
class GnbDuMeasurementReport:
    """DU 報 KPI 給 CU（每 N tick 一次）。"""
    ue_id: str
    rsrp_dbm: float
    sinr_db: float
    throughput_dl_mbps: float
    throughput_ul_mbps: float = 0.0
    mcs_dl: int = 0
    rb_width_dl: int = 0
    mimo_rank: int = 1
    # 累計 PDCP SDU bytes per window — 對齊 3GPP TS 28.552 DRB.PdcpSduVolumeDL/UL
    pdcp_sdu_volume_dl: int = 0
    pdcp_sdu_volume_ul: int = 0
    # 平均 RLC SDU 延遲 (ms) — 對齊 DRB.RlcSduDelayDl（暫不採集，預留）
    rlc_sdu_delay_dl_ms: float = 0.0
    # 2026-08-12(D):UE 的 5QI —— CU 端 delay/thp per-5QI 分桶用(AirIfDelayDlAvg.5QI1 轉真)
    qos_5qi: int = 9
    neighbor_cells: list[NeighborMeas] = field(default_factory=list)
    # P6 / P5-4(2026-09-14):上行與多層觀測。舊 DU 不帶 → CU 端存 None / 0 / []。
    mcs_ul: int = 0
    rb_width_ul: int = 0
    ul_sinr_db: float | None = None
    sinr_layers_db: list[float] = field(default_factory=list)
    # 2026-09-21:PM 視窗序號。歸檔原本依 CU 收到報告的「秒」分組,per_ue 又是以
    # ue_id 為鍵的字典 —— 2× 速度下每個 UE 每實際秒有兩份報告,後者直接覆蓋前者,
    # 實測丟掉 47%(2,000 列 → 1,066)。帶序號才能正確歸到同一個視窗。
    # 舊 DU 不帶 → CU 端存 None,歸檔退回舊的依秒分組。
    window_seq: int | None = None
    # B1(2026-09-16):O-RAN Cat B 的 GoB 波束(predefined-beam 的 beamId);None = 沒有 GoB
    beam_id: int | None = None
    # 2026-09-19:每波束 RSRP(O-RAN WG1 §4.6.4.1)。[[beam_id, 相對最佳波束的 dB], …],
    # 空 list = 沒有 GoB 或舊 DU。CU 用它做 per-beam 統計送 RIC。
    beam_rsrp_top: list = field(default_factory=list)


@dataclass
class GnbDuCellMeasurementReport:
    """AL2 — cell-level KPI per measurement window (對齊 3GPP TS 28.552 RRU.PrbTotDl).

    DU 每 N tick 算一次 cell-level PRB usage, 不從 per-UE sum 來 (避免 UE 樣本不齊造成 >100%).
    Cell-level PRB% = Σ(每 tick cell 全 UE 真實 PRB) / (tick_count × n_prb_total_per_tick)
    """
    cell_id: str
    prb_pct_dl: float          # 0~100, RRU.PrbTotDl
    prb_pct_ul: float = 0.0    # sim DL-only, 預留
    tick_count: int = 0        # window 內該 cell 的 tick 數
    window_seconds: float = 0.0
    # 與 per-UE 報告同一個序號,歸檔才併得到同一列(見 GnbDuMeasurementReport.window_seq)
    window_seq: int | None = None


@dataclass
class GnbDuConfigurationUpdate:
    """DU → CU：cell 配置變更通知（3GPP TS 38.473 §8.2.4 / §9.2.1.7）。

    對應 OAI 的 procedureCode=3（initiating message）：
      - openair2/F1AP/f1ap_handlers.c[3] = CU_handle_gNB_DU_CONFIGURATION_UPDATE
    F1Setup 之後若新增 / 修改 / 刪除 cell，DU 用這個訊息通知 CU。
    """
    gnb_du_id: int
    transaction_id: int = 0
    served_cells_to_add: list[CellConfig] = field(default_factory=list)
    served_cells_to_modify: list[CellConfig] = field(default_factory=list)
    served_cells_to_delete: list[str] = field(default_factory=list)  # cell_id list


@dataclass
class GnbDuConfigurationUpdateAcknowledge:
    """CU → DU：對 GnbDuConfigurationUpdate 的回應。"""
    transaction_id: int
    accepted: bool = True
