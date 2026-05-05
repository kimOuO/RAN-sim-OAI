"""從 DB 把 PathSolverRequest 拼出來 — 給 fapi_south.dl_tti_pipeline 用。

讀 antenna app 的 AntennaConfig / Cell / UePosition。
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Optional

from ran_sim_protocol.common import AntennaArrayConfig
from ran_sim_protocol.physics import (
    CellSpec,
    GnbSpec,
    PathSolverRequest,
    RxConfig,
    TxConfig,
    UeSpec,
)

from main.apps.antenna.models.antenna_config import AntennaConfig
from main.apps.antenna.models.cell import Cell
from main.apps.antenna.models.ue_position import UePosition


def latest_antenna_array() -> AntennaArrayConfig | None:
    qs = AntennaConfig.objects.order_by("-antenna_config_updated_at")
    a = qs.first()
    if a is None:
        return None
    return AntennaArrayConfig(
        rows=a.rows,
        cols=a.cols,
        polarization=a.polarization,
        pattern=a.pattern,
        vertical_spacing=a.vertical_spacing,
        horizontal_spacing=a.horizontal_spacing,
    )


def collect_ue_specs(ue_ids: Iterable[str]) -> list[UeSpec]:
    rows = UePosition.objects.filter(ue_id__in=list(ue_ids))
    return [
        UeSpec(
            id=r.ue_id,
            position=[r.position_x, r.position_y, r.position_z],
            velocity=[r.velocity_x, r.velocity_y, r.velocity_z],
        )
        for r in rows
    ]


def _cells_grouped_by_gnb() -> dict[str, list[Cell]]:
    """Cell.name 約定：`<gnb_name>` 或 `<gnb_name>#<pci>`（與 sionna_engine 約定相容）。"""
    out: dict[str, list[Cell]] = {}
    for c in Cell.objects.all():
        gnb_name = c.name.split("#", 1)[0]
        out.setdefault(gnb_name, []).append(c)
    return out


def build_tx_config() -> TxConfig:
    array = latest_antenna_array()
    if array is None:
        raise ValueError("AntennaConfig not set; call /update_antenna first")

    gnbs: list[GnbSpec] = []
    for gnb_name, cells in _cells_grouped_by_gnb().items():
        # 一個 gNB 的位置取第一個 cell（多 cell 共站時相同）
        head = cells[0]
        gnbs.append(
            GnbSpec(
                name=gnb_name,
                position=[head.position_x, head.position_y, head.position_z],
                cells=[CellSpec(pci=c.pci, azimuth_deg=c.azimuth_deg) for c in cells],
                frequency_ghz=head.frequency_ghz,
                bandwidth_mhz=head.bandwidth_mhz,
            )
        )
    return TxConfig(gnbs=gnbs, antenna_array=array)


def build_rx_config() -> RxConfig:
    """UE 端天線配置：暫用跟 gNB 一樣的 array（之後可以擴成獨立 UE array）。"""
    array = latest_antenna_array()
    if array is None:
        raise ValueError("AntennaConfig not set; call /update_antenna first")
    # UE 通常用更小的 array — 先給單天線版本
    ue_array = AntennaArrayConfig(
        rows=1,
        cols=1,
        polarization="V" if array.polarization in ("V", "H") else "VH",
        pattern="dipole",
    )
    return RxConfig(antenna_array=ue_array)


def build_path_solver_request(ue_ids: Iterable[str]) -> PathSolverRequest:
    return PathSolverRequest(
        ue_positions=collect_ue_specs(ue_ids),
        tx_config=build_tx_config(),
        rx_config=build_rx_config(),
    )
