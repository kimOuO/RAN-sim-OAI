"""FAPI-like message types — DU ↔ RU 介面。

對應 OAI: nfapi/, O-RAN 7.2x split, SCF FAPI specification (small cells forum)
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DlPduConfig:
    """DL TTI 中一個 PDU 的配置（一個 UE 在這 slot 收的東西）。"""
    ue_id: str
    prb_start: int
    prb_count: int
    mcs: int
    layers: int = 1
    pmi: int = 0  # codebook PMI index
    payload_size_bytes: int = 0
    harq_pid: int = 0
    # CU-CP RRC 是 serving cell 的 single source of truth (對齊 O-RAN 7.2x split)。
    # DU 從 _ue_registry[ue]['serving_cell'] 拿，emit 進 PDU 給 RU；
    # RU 不再用 Sionna argmax 自己挑，照 CU 認的 cell label 給 CqiIndication.
    # 空字串 = 舊行為 fallback 用 Sionna argmax (backward compat).
    cell_id: str = ""


@dataclass
class UlPduConfig:
    ue_id: str
    prb_start: int
    prb_count: int
    mcs: int
    layers: int = 1
    harq_pid: int = 0


@dataclass
class DlTtiRequest:
    """DU → RU：這 tick 對 UE X 發 PDU。"""
    sfn: int       # 0~1023
    slot: int      # 0~19 (numerology=1)
    pdus: list[DlPduConfig] = field(default_factory=list)


@dataclass
class UlTtiRequest:
    """DU → RU：這 tick 收 UE X 的 PUSCH。"""
    sfn: int
    slot: int
    pdus: list[UlPduConfig] = field(default_factory=list)


@dataclass
class CqiIndication:
    """RU → DU：UE 量到的 CQI/SINR/RSRP（真值來自 Sionna ray tracing）。"""
    ue_id: str
    sinr_db: float
    cqi: int       # 0~15
    rank: int = 1  # 1~4
    pmi: int = 0   # UE 推薦的 PMI
    # RSRP from path_gain (RU 端 dl_tti_pipeline 算)；
    # 預設 -200 表示未填（保持 backward compat），DU 收到 -200 會用估算 fallback。
    rsrp_dbm: float = -200.0
    serving_cell: str = ""  # RU 知道 UE serving cell（for context, not authoritative）
    # Neighbor cell measurements — 給 A3 evaluator 用
    # 對齊 3GPP TS 38.331 §5.5.4.4 — 每個 neighbor 帶 cell_id + RSRP，A3 比較用
    neighbors: list = field(default_factory=list)
    """每筆 dict: {cell_id: str, rsrp_dbm: float, rsrq_db: float = 0.0}.
    Type 不寫 NeighborMeas 因為 dataclass + JSON 序列化路徑，list[dict] 通用。"""


@dataclass
class CrcIndication:
    """RU → DU：UL CRC 結果（給 HARQ 用）。"""
    ue_id: str
    harq_pid: int
    success: bool
