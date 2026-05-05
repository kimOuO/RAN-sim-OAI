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
    neighbor_cells: list[NeighborMeas] = field(default_factory=list)


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
