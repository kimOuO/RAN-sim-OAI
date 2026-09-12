"""E1AP message types — CU-CP ↔ CU-UP 介面（CU 內部）。

對應 OAI: openair2/E1AP/, 3GPP TS 38.463
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ran_sim_protocol.common import DrbConfig


@dataclass
class DrbSetupResult:
    drb_id: int
    success: bool
    cu_up_tunnel_addr: str = ""
    cu_up_teid: int = 0


@dataclass
class BearerContextSetupRequest:
    """CU-CP → CU-UP：建立 bearer。"""
    ue_id: str
    drbs: list[DrbConfig] = field(default_factory=list)


@dataclass
class BearerContextSetupResponse:
    """CU-UP → CU-CP：bearer 建立結果。"""
    ue_id: str
    drb_setup_list: list[DrbSetupResult] = field(default_factory=list)


@dataclass
class BearerContextRelease:
    ue_id: str
    cause: str = "normal"
