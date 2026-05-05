"""Common dataclass shared across F1AP / FAPI / NGAP / E1AP / Physics."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CellConfig:
    cell_id: str
    pci: int
    frequency_ghz: float
    bandwidth_mhz: float
    served_plmn: str = "00101"


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
