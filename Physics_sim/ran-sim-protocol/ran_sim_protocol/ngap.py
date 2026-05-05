"""NGAP message types — CU ↔ Mock 5GC 介面。

對應 OAI: openair3/NGAP/, 3GPP TS 38.413
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PduSessionResource:
    pdu_session_id: int
    qos_flow_5qi: list[int] = field(default_factory=list)
    s_nssai: str = "01:000000"  # slice id (sst:sd)


@dataclass
class NgSetupRequest:
    """CU 啟動時送 mock 5GC。"""
    gnb_id: int
    plmn_id: str
    served_tac: list[int] = field(default_factory=list)


@dataclass
class NgSetupResponse:
    amf_name: str
    served_guami_list: list[str] = field(default_factory=list)


@dataclass
class InitialUeMessage:
    """UE attach：CU → 5GC。"""
    ran_ue_ngap_id: int
    nas_pdu_b64: str
    selected_plmn: str = "00101"


@dataclass
class InitialContextSetupRequest:
    """5GC → CU：建立 UE context。"""
    ran_ue_ngap_id: int
    amf_ue_ngap_id: int
    pdu_session_resources: list[PduSessionResource] = field(default_factory=list)


@dataclass
class DownlinkNasTransport:
    """5GC → CU → UE 的 NAS 訊息。"""
    ran_ue_ngap_id: int
    amf_ue_ngap_id: int
    nas_pdu_b64: str


@dataclass
class UplinkNasTransport:
    """UE → CU → 5GC。"""
    ran_ue_ngap_id: int
    amf_ue_ngap_id: int
    nas_pdu_b64: str
