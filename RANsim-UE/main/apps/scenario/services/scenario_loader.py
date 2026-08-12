"""從 Omniverse 抓 scenario JSON 並 parse 成可 driver 用的結構。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


OMNIVERSE_URL = os.environ.get("OMNIVERSE_URL", "http://host.docker.internal:8001")
# 劇本/場景來源切換:預設沿用 Omniverse;設 SCENARIO_STORE_URL(如 Physics :8104)
# 即可讓 sim 脫離 Omniverse。端點與回應形狀相同,只換 base URL。
SCENARIO_STORE_URL = os.environ.get("SCENARIO_STORE_URL") or OMNIVERSE_URL


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
    # per-cell 頻率覆寫(None = 繼承所屬 gNB 的 frequency_ghz)。
    # 對齊 OAI「1 gNB + 2 DU 異頻」(pci0=3.45 / pci1=3.65);有給時干擾改走頻率重疊判斷。
    frequency_ghz: float | None = None
    bandwidth_mhz: float | None = None


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
    bandwidth_mhz: float = 40.0
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
    # Optional 劇本自帶 per-cell PRB quota,start() 時自動套用(= xApp E2 Control Style2/Action6)。
    # [{"cell_id": str, "max_prb": int(0-100)}, ...]。CCO 容量受限 demo 用(c0 設 20%)。
    cell_quotas: list[dict] = None  # type: ignore[assignment]
    # per-scenario 物理參數(劇本 start 套用,免 DU 專用 env)。缺省 = 一般 co-channel 預設。
    inter_freq: bool = False          # True = 不同頻不互擾(CCO 用)
    discard_timer_ms: int = 300       # 0 = 關(CCO 讓 delay 真實爬);一般 300
    tx_power_dbm: float = 23.0         # CCO 邊界要好 SINR 時拉高(如 33)
    # A3 自動換手開關。None = 不覆寫(用 CU env HO_A3_ENABLED,預設 off)。
    # CCO 等「RC 手動換到較弱 cell」的 demo 要 False,否則 A3 看訊號把人彈回強 cell。
    a3_enabled: bool | None = None
    # A3 門檻(None = 用 CU env 預設 offset5+hys6=11dB)。ANR 缺漏鄰區 demo 用 offset2+hys1。
    a3_offset_db: float | None = None
    a3_hys_db: float | None = None
    a3_ttt_ms: int | None = None
    # RLC delay 模式:'calib'(÷30 對齊 OAI 低 delay)| 'subtick'(誠實佇列延遲)。
    # CCO 要 subtick 壅塞 delay 才爬得過 500ms 門檻;OAI 對照劇本用 calib。
    rlc_delay_model: str = "calib"
    # 劇本 _metadata.trigger_config:dashboard 觸發門檻的單一來源(改劇本→前端自動跟)。
    # 不解讀內容,原樣透傳給前端 evaluator(key 對齊前端 TRIGGER_THRESHOLDS)。
    trigger_config: dict | None = None

    def __post_init__(self):
        if self.gnbs is None:
            self.gnbs = []
        if self.buildings is None:
            self.buildings = []
        if self.cell_quotas is None:
            self.cell_quotas = []

    @property
    def total_ticks(self) -> int:
        return int(self.duration_sec * 1000 // self.tick_ms)


def fetch(scenario_id: str) -> ScenarioSpec:
    """從劇本來源(SCENARIO_STORE_URL,預設 Omniverse)抓 raw_json,parse 成 ScenarioSpec。"""
    r = requests.post(
        f"{SCENARIO_STORE_URL}/api/v0.1/RAN/Scenario/ScenarioController/read",
        json={"scenario_id": scenario_id},
        timeout=10,
    )
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(f"Omniverse Scenario read failed: {body}")
    data = body["data"]
    raw = data.get("raw_json") or {}

    _dur = float(raw.get("duration_sec") or 0.0)
    ues = [
        UeScenarioRow(name=str(u["name"]),
                      positions=_normalize_positions(list(u.get("positions") or []), _dur))
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
                frequency_ghz=(float(c["frequency_ghz"]) if c.get("frequency_ghz") is not None else None),
                bandwidth_mhz=(float(c["bandwidth_mhz"]) if c.get("bandwidth_mhz") is not None else None),
            ))
        gnbs.append(GnbScenarioRow(
            name=str(g["name"]),
            position=(float(pos[0]), float(pos[1]), float(pos[2])),
            frequency_ghz=float(g.get("frequency_ghz") or 3.5),
            bandwidth_mhz=float(g.get("bandwidth_mhz") or 40.0),
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
        cell_quotas=[
            {"cell_id": str(q["cell_id"]), "max_prb": int(q.get("max_prb", 100)),
             "min_prb": int(q.get("min_prb", 0))}
            for q in (raw.get("cell_quotas") or []) if q.get("cell_id")
        ],
        inter_freq=bool(raw.get("inter_freq", False)),
        discard_timer_ms=int(raw.get("discard_timer_ms", 300)),
        tx_power_dbm=float(raw.get("tx_power_dbm", 23.0)),
        a3_enabled=(None if raw.get("a3_enabled") is None else bool(raw.get("a3_enabled"))),
        a3_offset_db=(None if raw.get("a3_offset_db") is None else float(raw["a3_offset_db"])),
        a3_hys_db=(None if raw.get("a3_hys_db") is None else float(raw["a3_hys_db"])),
        a3_ttt_ms=(None if raw.get("a3_ttt_ms") is None else int(raw["a3_ttt_ms"])),
        rlc_delay_model=str(raw.get("rlc_delay_model") or "calib"),
        trigger_config=((raw.get("_metadata") or {}).get("trigger_config") or None),
    )


def _normalize_positions(positions: list[list[float]], duration_sec: float) -> list[list[float]]:
    """劇本 UE positions 容錯 → 統一成 `[[t, x, y, z], ...]`。

    - 4 值 `[t,x,y,z]`(das_test 格式）→ 原樣。
    - 3 值 `[x,y,z]`（Omniverse/editor/ANR 劇本格式,無時間軸)→ 依 `duration_sec`
      平均補時間軸:第一點 t=0、最後點 t=duration_sec,UE 在整個劇本時長內走完 waypoints。
      duration 未設時退回「每段 1 秒」。單一 waypoint → t=0(靜止)。
    """
    if not positions:
        return positions
    if len(positions[0]) >= 4:
        return positions
    n = len(positions)
    if n == 1:
        return [[0.0, float(positions[0][0]), float(positions[0][1]), float(positions[0][2])]]
    dur = duration_sec if (duration_sec and duration_sec > 0) else float(n - 1)
    return [[round(dur * i / (n - 1), 3), float(p[0]), float(p[1]), float(p[2])]
            for i, p in enumerate(positions)]


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


def waypoints_with_speed_to_trajectory(
    waypoints: list[list[float]],
    speed_mps: float,
) -> list[dict[str, float]]:
    """Omniverse UeConfig `[[x,y,z], ...] + speed_mps` → trajectory waypoints `[{x,y,z,t_ms}, ...]`.

    用途:讓 /editor 拉拖的 UE 軌跡(沒時間軸,只有 waypoint+速度)走跟劇本同一個
    trajectory_store / interp.interp_position 機制。t_ms 從累積距離 / speed 算。

    第一個 waypoint t_ms=0。之後 t_ms[i] = t_ms[i-1] + dist(wp[i-1], wp[i]) / speed_mps × 1000。
    speed_mps <= 0 或 waypoints < 2 → 回空 list(caller skip 不推 store)。
    """
    if not waypoints or len(waypoints) < 2 or speed_mps <= 0:
        return []
    out: list[dict[str, float]] = []
    t_ms_acc = 0.0
    prev: list[float] | None = None
    for wp in waypoints:
        if len(wp) < 3:
            continue
        x, y, z = float(wp[0]), float(wp[1]), float(wp[2])
        if prev is None:
            out.append({"x": x, "y": y, "z": z, "t_ms": 0})
        else:
            dx = x - prev[0]
            dy = y - prev[1]
            dz = z - prev[2]
            dist = (dx * dx + dy * dy + dz * dz) ** 0.5
            t_ms_acc += dist / speed_mps * 1000.0
            out.append({"x": x, "y": y, "z": z, "t_ms": int(t_ms_acc)})
        prev = [x, y, z]
    return out


def positions_to_waypoints(positions: list[list[float]]) -> list[dict[str, float]]:
    """劇本 `[[t_sec, x, y, z], ...]` → trajectory_store 用的 `[{x,y,z,t_ms}, ...]`。

    用途:讓劇本 UE 走 UeLifecycleManager._trajectory_loop 既有的位置內插 +
    RU 推送機制(共用 interp.interp_position),不再走 scenario_driver 自己的
    tick loop。

    僅做格式轉換,不做 sanity check / sort — 假設劇本 raw_json 已經是時間遞增。
    interp.interp_position 對非單調 t 也只是 fallback first / last,不會崩。
    """
    return [
        {
            "x": float(p[1]),
            "y": float(p[2]),
            "z": float(p[3]),
            "t_ms": int(float(p[0]) * 1000),
        }
        for p in positions
        if len(p) >= 4
    ]


