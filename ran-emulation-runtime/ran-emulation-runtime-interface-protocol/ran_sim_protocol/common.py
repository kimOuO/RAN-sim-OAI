"""Common dataclass shared across F1AP / FAPI / NGAP / E1AP / Physics."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _default_plmn() -> str:
    # 從 env 組 served_plmn,避免散落各處硬編 "00101"。
    # 沒設 env 時 fallback 到 3GPP 測試 PLMN "00101"。
    mcc = os.environ.get("PLMN_MCC", "001")
    mnc = os.environ.get("PLMN_MNC", "01")
    return f"{mcc}{mnc}"


@dataclass
class CellConfig:
    cell_id: str
    pci: int
    frequency_ghz: float
    bandwidth_mhz: float
    served_plmn: str = field(default_factory=_default_plmn)
    gnb_id: str = ""
    is_active: bool = True
    # OAI 真實 nr_cellid (36-bit int) 對齊用;空值時走 SHA-1 hash fallback。
    nr_cellid: int | None = None


@dataclass
class DrbConfig:
    drb_id: int
    qos_5qi: int
    rlc_mode: str = "AM"  # "AM" | "UM" | "TM"


@dataclass
class NeighborMeas:
    cell_id: str
    rsrp_dbm: float
    rsrq_db: float


@dataclass
class AntennaArrayConfig:
    rows: int
    cols: int
    polarization: str = "V"  # "V" | "H" | "VH" | "cross"
    pattern: str = "tr38901"  # "tr38901" | "dipole" | "iso" | "hw_dipole" | "vh_dipole"
    vertical_spacing: float = 0.5
    horizontal_spacing: float = 0.5
