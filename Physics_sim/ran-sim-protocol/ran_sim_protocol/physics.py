"""Physics REST API request/response types — RU → Physics 通訊。

不對應 OAI（OAI 用 statistical TDL）；這是 RAN-sim 平台特有的物理模擬服務。
Endpoint: POST /api/v0.1/Physics/RanCalc/PathSolver/compute
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ran_sim_protocol.common import AntennaArrayConfig


@dataclass
class CellSpec:
    """RU 上某一個 cell 的設定（給 Sionna 知道 azimuth）。"""
    pci: int
    azimuth_deg: float = 0.0


@dataclass
class GnbSpec:
    """Physics 觀點下的 gNB（包括位置 + cells）。"""
    name: str
    position: list[float]                  # [x, y, z] meters
    cells: list[CellSpec] = field(default_factory=list)
    power_dbm: float = 30.0
    frequency_ghz: float = 2.5
    bandwidth_mhz: float = 100.0


@dataclass
class UeSpec:
    """Physics 觀點下的 UE（位置 + 速度）。"""
    id: str
    position: list[float]                  # [x, y, z]
    velocity: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])


@dataclass
class TxConfig:
    """發射端配置。"""
    gnbs: list[GnbSpec]
    antenna_array: AntennaArrayConfig


@dataclass
class RxConfig:
    """接收端配置（UE 共用一組陣列配置）。"""
    antenna_array: AntennaArrayConfig


@dataclass
class PathSolverRequest:
    """RU → Physics。"""
    ue_positions: list[UeSpec]
    tx_config: TxConfig
    rx_config: RxConfig


@dataclass
class PathSolverResponse:
    """Physics → RU。

    channel_matrix: nested dict {ue_id: {gnb_name: complex_matrix}}
    path_gain:      nested dict {ue_id: {gnb_name: float (linear)}}
    serving_cells:  flat dict   {ue_id: gnb_name}
    """
    channel_matrix: dict
    path_gain: dict
    serving_cells: dict
