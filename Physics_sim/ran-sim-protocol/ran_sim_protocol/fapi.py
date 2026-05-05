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
    """RU → DU：UE 量到的 CQI/SINR。"""
    ue_id: str
    sinr_db: float
    cqi: int       # 0~15
    rank: int = 1  # 1~4
    pmi: int = 0   # UE 推薦的 PMI


@dataclass
class CrcIndication:
    """RU → DU：UL CRC 結果（給 HARQ 用）。"""
    ue_id: str
    harq_pid: int
    success: bool
