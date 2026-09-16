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
    # 每 cell 上一 tick 的 UL PRB 負載 0–1(P6):RU 算鄰 cell UE 對我 gNB 的上行干擾時當「同 PRB 碰撞機率」。
    # 空 dict = 舊 DU,RU 退回 env RU_UL_NEIGHBOR_LOAD。
    cell_ul_load: dict[str, float] = field(default_factory=dict)


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
    # 每層 SINR(dB,長度 = rank;由 H 的奇異值推:第 i 層 = 總 SINR − 10log10(rank) + 20log10(σi/σ1))。
    # 空 list = 舊 RU 沒帶,DU 退回等功率近似(每層 −10log10 rank)。2026-09-13 P5-4。
    sinr_per_layer_db: list[float] = field(default_factory=list)
    # 上行 SINR@gNB(dB;P6 2026-09-13):TDD 互易 pg(UE→gNB)=pg(gNB→UE),UE 開迴路功控,鄰 cell UE 依 UL 負載當干擾。
    # None = 舊 RU 沒帶 → DU 退回 DL SINR − 20 dB 的保守近似(以前是直接 = DL SINR)。
    ul_sinr_db: float | None = None
    # B1(2026-09-16):O-RAN Cat B 的 GoB 波束。beam_id = O-RU 波束表的索引(predefined-beam 的 beamId);
    # beam_rsrp_top = [(beam_id, 相對最佳波束的 dB 差), …],給 RIC 的每波束 RSRP 統計(O-RAN WG1 §4.6.4.1)。
    # None / 空 list = 沒有 GoB(單埠或 Cat A 未設定)。
    beam_id: int | None = None
    beam_rsrp_top: list = field(default_factory=list)
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
