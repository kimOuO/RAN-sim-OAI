"""從 Omniverse 抓 scenario JSON 並 parse 成可 driver 用的結構。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


OMNIVERSE_URL = os.environ.get("OMNIVERSE_URL", "http://host.docker.internal:8001")


@dataclass
class UeScenarioRow:
    name: str
    positions: list[list[float]]  # [[t, x, y, z], ...]


@dataclass
class TrafficScenarioRow:
    ue_name: str
    profile: list[list[float]]  # [[t, dl_kbps, ul_kbps], ...]


@dataclass
class CellScenarioRow:
    """劇本指定的 cell 設定 — 一個 gNB 下的一個 sector。

    position 是 optional override(DAS / multi-TRP 場景需要 cell 物理分離),
    沒給就 fallback 到所屬 gNB 的 position。
    """
    cell_id: str
    pci: int = 0
    azimuth_deg: float = 0.0   # 0 = 正北,90 = 正東
    position: tuple[float, float, float] | None = None


@dataclass
class BuildingScenarioRow:
    """劇本可指定建築拓樸,跟 UE/gNB 同概念。USD 統一走 Brownstone 01 不在這層指定
    (走 omniverse_client.create_building 帶 preset_id="brownstone01")。

    size / color / rotation_xyz_deg / target_height_m 都允許 None — 表示「劇本沒指定」,
    upsert 時這些 key 不會出現在 payload 裡,backend BuildingWriteSerializer 就會去
    UsdAsset(preset_id="brownstone01") 撈 default_size / default_color / default_rotation,
    跟前端 /editor 用 Build 拉同個 preset 時行為一致。
    """
    name: str
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    size: tuple[float, float, float] | None = None
    color: tuple[float, float, float] | None = None
    rotation_xyz_deg: tuple[float, float, float] | None = None
    material: str = ""
    target_height_m: float | None = None


@dataclass
class GnbScenarioRow:
    """劇本可指定 gNB 拓樸,覆寫 scene_config.json + Omniverse DB。"""
    name: str
    position: tuple[float, float, float]            # (x, y, z)
    frequency_ghz: float = 3.5
    bandwidth_mhz: float = 100.0
    power_dbm: float = 23.0
    active: bool = True
    color: tuple[float, float, float] = (0.2, 0.8, 0.4)
    target_height_m: float | None = None
    cells: list[CellScenarioRow] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.cells is None:
            self.cells = []


@dataclass
class ScenarioSpec:
    scenario_id: str
    scene_id: str
    duration_sec: float
    tick_ms: int           # 母 scenario 的 sim-time 一個 tick 多長(對應 DU sim_dt_ms)
    ues: list[UeScenarioRow]
    traffic: list[TrafficScenarioRow]
    default_serving_cell: str = "gnb1_cell0"   # driver 自動 attach 用,scenario 可覆寫
    gnbs: list[GnbScenarioRow] = None  # type: ignore[assignment]
    buildings: list[BuildingScenarioRow] = None  # type: ignore[assignment]
    # 從 Scenario model 帶出的 precompute 狀態,driver.start() 用來決定 RU mode:
    # ready  → 切 RU 到 cached + 載這 scenario 的 npz
    # 其他   → 切 RU 到 live(走即時 Sionna)
    precompute_status: str = "pending"
    # Optional scenario-level antenna pattern override(觸發 Sionna scene rebuild)。
    # None = 不覆寫,用 Physics env default(typically tr38901 sector)。
    # "iso" / "dipole" / "tr38901" 是 Sionna 內建可用 patterns。
    # 注意:這是 scenario-level 全局設定,sionna scene.tx_array 不支援 per-cell pattern。
    antenna_pattern: str | None = None

    def __post_init__(self):
        if self.gnbs is None:
            self.gnbs = []
        if self.buildings is None:
            self.buildings = []

    @property
    def total_ticks(self) -> int:
        return int(self.duration_sec * 1000 // self.tick_ms)


def fetch(scenario_id: str) -> ScenarioSpec:
    """從 Omniverse Scenario API 抓 raw_json,parse 成 ScenarioSpec。"""
    r = requests.post(
        f"{OMNIVERSE_URL}/api/v0.1/RAN/Scenario/ScenarioController/read",
        json={"scenario_id": scenario_id},
        timeout=10,
    )
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(f"Omniverse Scenario read failed: {body}")
    data = body["data"]
    raw = data.get("raw_json") or {}

    ues = [
        UeScenarioRow(name=str(u["name"]), positions=list(u.get("positions") or []))
        for u in raw.get("ues") or []
    ]
    traffic = [
        TrafficScenarioRow(
            ue_name=str(t["ue_name"]), profile=list(t.get("profile") or []),
        )
        for t in raw.get("traffic") or []
    ]
    # Parse gnbs(optional) — 劇本可指定 gNB 拓樸覆寫 scene_config
    gnbs: list[GnbScenarioRow] = []
    for g in raw.get("gnbs") or []:
        pos = g.get("position") or [0.0, 0.0, 0.0]
        cells_raw = g.get("cells") or []
        cells = []
        for c in cells_raw:
            cell_pos_raw = c.get("position")
            cell_pos: tuple[float, float, float] | None = None
            if cell_pos_raw:
                cell_pos = (float(cell_pos_raw[0]), float(cell_pos_raw[1]), float(cell_pos_raw[2]))
            cells.append(CellScenarioRow(
                cell_id=str(c["cell_id"]),
                pci=int(c.get("pci") or 0),
                azimuth_deg=float(c.get("azimuth_deg") or 0.0),
                position=cell_pos,
            ))
        gnbs.append(GnbScenarioRow(
            name=str(g["name"]),
            position=(float(pos[0]), float(pos[1]), float(pos[2])),
            frequency_ghz=float(g.get("frequency_ghz") or 3.5),
            bandwidth_mhz=float(g.get("bandwidth_mhz") or 100.0),
            power_dbm=float(g.get("power_dbm") or 23.0),
            active=bool(g.get("active", True)),
            color=tuple(g.get("color") or [0.2, 0.8, 0.4]),  # type: ignore[arg-type]
            target_height_m=g.get("target_height_m"),
            cells=cells,
        ))
    # Parse buildings(optional) — 劇本可指定建築拓樸覆寫場景。
    # size / color / rotation_xyz_deg 三個欄位「沒寫」跟「寫了空值」分開處理:
    # 沒寫 → 保留 None → upsert payload 不帶這 key → backend 套 brownstone01 preset 預設
    # 寫了 → 照劇本走
    buildings: list[BuildingScenarioRow] = []
    for b in raw.get("buildings") or []:
        pos = b.get("position") or [0.0, 0.0, 0.0]
        size_raw = b.get("size")
        col_raw = b.get("color")
        rot_raw = b.get("rotation_xyz_deg")
        buildings.append(BuildingScenarioRow(
            name=str(b["name"]),
            position=(float(pos[0]), float(pos[1]), float(pos[2])),
            size=(float(size_raw[0]), float(size_raw[1]), float(size_raw[2])) if size_raw else None,
            color=(float(col_raw[0]), float(col_raw[1]), float(col_raw[2])) if col_raw else None,
            rotation_xyz_deg=(float(rot_raw[0]), float(rot_raw[1]), float(rot_raw[2])) if rot_raw else None,
            material=str(b.get("material") or ""),
            target_height_m=b.get("target_height_m"),
        ))
    antenna_pattern_raw = raw.get("antenna_pattern")
    antenna_pattern = str(antenna_pattern_raw) if antenna_pattern_raw else None
    return ScenarioSpec(
        scenario_id=str(raw.get("scenario_id") or scenario_id),
        scene_id=str(raw.get("scene_id") or ""),
        duration_sec=float(raw.get("duration_sec") or 0.0),
        tick_ms=int(raw.get("tick_ms") or 500),
        ues=ues,
        traffic=traffic,
        default_serving_cell=str(raw.get("default_serving_cell") or "gnb1_cell0"),
        gnbs=gnbs,
        buildings=buildings,
        # precompute_status 來自 Scenario model 本體欄位(不在 raw_json 裡)
        precompute_status=str(data.get("precompute_status") or "pending"),
        antenna_pattern=antenna_pattern,
    )


def interpolate_position(positions: list[list[float]], t_sec: float) -> tuple[float, float, float]:
    """linear interp,t 超出範圍 clamp。"""
    if not positions:
        return (0.0, 0.0, 0.0)
    if t_sec <= positions[0][0]:
        p = positions[0]
        return (p[1], p[2], p[3])
    if t_sec >= positions[-1][0]:
        p = positions[-1]
        return (p[1], p[2], p[3])
    for i in range(len(positions) - 1):
        if positions[i][0] <= t_sec <= positions[i + 1][0]:
            t0, x0, y0, z0 = positions[i]
            t1, x1, y1, z1 = positions[i + 1]
            if t1 == t0:
                return (x0, y0, z0)
            r = (t_sec - t0) / (t1 - t0)
            return (x0 + (x1 - x0) * r, y0 + (y1 - y0) * r, z0 + (z1 - z0) * r)
    return (positions[-1][1], positions[-1][2], positions[-1][3])


def interpolate_traffic(profile: list[list[float]], t_sec: float) -> tuple[float, float]:
    """piecewise-constant 不內插 — t 落在 [t_i, t_{i+1}) 區間取 t_i 的值。
    回傳 (dl_kbps, ul_kbps)。
    """
    if not profile:
        return (0.0, 0.0)
    if t_sec < profile[0][0]:
        return (0.0, 0.0)
    last = profile[0]
    for p in profile:
        if p[0] > t_sec:
            break
        last = p
    return (float(last[1]) if len(last) > 1 else 0.0,
            float(last[2]) if len(last) > 2 else 0.0)
