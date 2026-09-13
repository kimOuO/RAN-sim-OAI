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

from main.utils.env_loader import get_int, get_str
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
    from ran_sim_protocol.cell_tag import strip_tag
    for c in Cell.objects.all():
        gnb_name = strip_tag(c.name).split("#", 1)[0]   # run 標籤不進 Sionna 的 tx 名
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
    """UE 端天線配置。

    2026-09-11:原本硬編 rows=1/cols=1(註解自承「先給單天線版本」),使 H 恆為
    1×N → SVD rank 恆為 1 → 多天線與空間多工完全無法出現。改為可由環境變數指定,
    為天線選擇研究預留。

    ⚠ 目前 Physics 的 `path_solver_actor` 仍會**忽略** rx_config/tx_config
      (陣列在 init_scene 階段 baked-in),所以本設定尚不會生效。
      打通計畫見 docs/architecture/mimo_antenna_selection_plan.md §3。
    """
    array = latest_antenna_array()
    if array is None:
        raise ValueError("AntennaConfig not set; call /update_antenna first")
    ue_array = AntennaArrayConfig(
        rows=get_int("UE_ARRAY_ROWS", 1),
        cols=get_int("UE_ARRAY_COLS", 1),
        polarization=get_str(
            "UE_ARRAY_POLARIZATION",
            "V" if array.polarization in ("V", "H") else "VH",
        ),
        pattern=get_str("UE_ARRAY_PATTERN", "dipole"),
    )
    return RxConfig(antenna_array=ue_array)


def build_path_solver_request(ue_ids: Iterable[str]) -> PathSolverRequest:
    return PathSolverRequest(
        ue_positions=collect_ue_specs(ue_ids),
        tx_config=build_tx_config(),
        rx_config=build_rx_config(),
    )
