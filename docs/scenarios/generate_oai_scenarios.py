#!/usr/bin/env python3
"""把 OAI 三個 traffic 劇本(im/cco/es)轉成 Phase B fast-replay scenario JSON。

OAI 端的劇本是 wall-clock 真打流量(iperf3 / ping);Phase B 在 DT 上
用 scenario JSON 的 traffic profile + UE 位置時間軸表達同樣的 KPM
觸發條件,然後跑 Sionna precompute + cached fast run,就能用 1/N
的 wall-clock 重現等價條件給 xApp 看。

跑法:
    python3 docs/scenarios/generate_oai_scenarios.py
    → 產出 docs/scenarios/{im,cco,es}_fast.json

對應原始 OAI 劇本的關鍵參數:
    im_traffic.sh:DL_RATE=3M / DURATION_S=90 / UL_PING_PARALLEL=3
    cco_traffic.sh:DL_RATE=1.5M / DURATION_S=120
    es_traffic.sh:TRIGGER_WAIT_S=120 / RECOVERY_RATE=2M / RECOVERY_DURATION_S=60
"""
from __future__ import annotations

import json
from pathlib import Path

OUT_DIR = Path(__file__).parent
SCENE_ID = "twocell_1gnb"   # 1 gNB gnbDT 在 (0,30,0) — 2 cells c0(azimuth 0°朝北) c1(azimuth 180°朝南)
TICK_MS = 500
DEFAULT_SERVING_CELL = "gnbDT_c0"

# 兩個 sector 覆蓋的座標範圍(以 gNB 為中心,北邊正 z 方向、南邊負 z)
NORTH_NEAR  = (0.0, 1.5,  60.0)   # c0 覆蓋核心
NORTH_FAR   = (0.0, 1.5, 150.0)   # c0 覆蓋邊緣(訊號弱)
SOUTH_NEAR  = (0.0, 1.5, -60.0)   # c1 覆蓋核心
SOUTH_FAR   = (0.0, 1.5, -150.0)  # c1 覆蓋邊緣(訊號弱)

# Brownstone scene gNB 位置(來自 scene_config.json)
# NW    = ( 200, 50,  200)
# SE    = (-200, 45, -200)
# CENT  = (   0, 30,    0)
NW = (200.0, 1.5, 200.0)         # UE 在地面上(1.5m 高)
NW_EDGE = (260.0, 1.5, 260.0)    # NW 外圍 → 弱訊號
NW_NEAR = (180.0, 1.5, 180.0)    # NW 附近
SE = (-200.0, 1.5, -200.0)
CENT = (0.0, 1.5, 0.0)


# ─── 標準 gNB 拓樸(所有 6 個劇本共用)──────────────────────────
# 1 gNB gnbDT,2 cells:c0 朝北(0°), c1 朝南(180°)
# 對齊 asset registry:gNB → Standard gNB / cell 用 Kit 內建 cone+antenna
BASE_GNBS = [
    {
        "name": "gnbDT",
        "position": [0, 30, 0],
        "frequency_ghz": 3.5,
        "bandwidth_mhz": 100,
        "power_dbm": 23,
        "active": True,
        "color": [0.2, 0.8, 0.4],
        "cells": [
            {"cell_id": "gnbDT_c0", "pci": 0, "azimuth_deg": 0},
            {"cell_id": "gnbDT_c1", "pci": 1, "azimuth_deg": 180},
        ],
    },
]


# ─── 標準建築拓樸 ────────────────────────────────────────────────
# 所有劇本一律不帶建築 — 起跑時不覆寫 Omniverse DB 既有的 BuildingConfig,沿用前端
# /editor 拉好的場景。要在劇本層級指定建築,在各 scenario 函式 return 的 dict 內
# 個別塞 "buildings": [{name, position, ...}]。
# (DB / Sionna scene_config.json 的建築本身不動,只是劇本不再自帶。)
BASE_BUILDINGS: list = []


# ─── IM scenario ──────────────────────────────────────────────────
# 設計:UE 固定在 c0 覆蓋邊緣(NORTH_FAR)→ 弱 RSRP / 低 MCS
# DL 3 Mbps + UL 672 kbps → PRB 滿但 throughput 撐不起 → RLC 延遲累積
def im_scenario(duration_sec: int = 60) -> dict:
    return {
        "scenario_id": "im_fast",
        "scene_id": SCENE_ID,
        "duration_sec": duration_sec,
        "tick_ms": TICK_MS,
        "default_serving_cell": DEFAULT_SERVING_CELL,
        "ues": [
            {
                "name": "im_ue_01",
                "positions": [
                    [0,            NORTH_FAR[0], NORTH_FAR[1], NORTH_FAR[2]],
                    [duration_sec, NORTH_FAR[0], NORTH_FAR[1], NORTH_FAR[2]],
                ],
            },
        ],
        "traffic": [
            {
                "ue_name": "im_ue_01",
                # DL 3000 kbps / UL 672 kbps(對應 3 × 1400B / 0.05s ping)
                # 全程恆定 → 對應 OAI 劇本 90s 持續壓
                "profile": [[0, 3000, 672]],
            },
        ],
        "_metadata": {
            "oai_origin": "im_traffic.sh",
            "intent": "IM (interference mitigation)",
            "required_topology": {
                "min_gnbs": 1, "min_cells_per_gnb": 1, "min_ues": 1,
                "rationale": "單 cell 內擁塞 — 1 gNB 1 cell 1 UE 即可",
            },
            "expected_kpm": {
                "RRU.PrbTotDl": "> 0.70",
                "DRB.UEThpDl": "< 5000 kbps (channel-limited)",
                "DRB.RlcSduDelayDl": "> 50 ms",
            },
            "xapp_expected_action": "control_slice_level_prb_quota (style=2 action=6)",
        },
    }


# ─── CCO scenario ─────────────────────────────────────────────────
# 改成「同 gNB 內 cross-cell handover」(對應 1 gNB 2 cell 場景)
# 設計:UE 從 NORTH(c0 強)走到 SOUTH(c1 強),中途經過 gNB 正下方
# 三階段:前 1/3 在 c0、中 1/3 過渡、後 1/3 在 c1。1.5 Mbps DL 全程。
# 期待:前段 c0 PRB 高、c1=0;handover 後 c1 PRB 高、c0=0
def cco_scenario(duration_sec: int = 60) -> dict:
    t_mid_start = duration_sec * 1 // 3
    t_mid_end   = duration_sec * 2 // 3
    return {
        "scenario_id": "cco_fast",
        "scene_id": SCENE_ID,
        "duration_sec": duration_sec,
        "tick_ms": TICK_MS,
        "default_serving_cell": DEFAULT_SERVING_CELL,
        "ues": [
            {
                "name": "cco_ue_01",
                "positions": [
                    [0,             NORTH_NEAR[0], NORTH_NEAR[1], NORTH_NEAR[2]],
                    [t_mid_start,   NORTH_NEAR[0], NORTH_NEAR[1], NORTH_NEAR[2]],
                    [t_mid_end,     SOUTH_NEAR[0], SOUTH_NEAR[1], SOUTH_NEAR[2]],
                    [duration_sec,  SOUTH_NEAR[0], SOUTH_NEAR[1], SOUTH_NEAR[2]],
                ],
            },
        ],
        "traffic": [
            {
                "ue_name": "cco_ue_01",
                "profile": [[0, 1500, 100]],
            },
        ],
        "_metadata": {
            "oai_origin": "cco_traffic.sh (adapted: cross-cell within same gNB)",
            "intent": "CCO (intra-gNB cell handover load-balance)",
            "required_topology": {
                "min_gnbs": 1, "min_cells_per_gnb": 2, "min_ues": 1,
                "rationale": "Cell 間 PRB 失衡 — 1 gNB 2 cells 即可(原 OAI 是跨 gNB,這版改為同 gNB 內 cross-cell)",
            },
            "expected_kpm": {
                f"phase 0~{t_mid_start}s": "c0 PRB > 50, c1 PRB ≈ 0",
                f"phase {t_mid_end}~{duration_sec}s": "c1 PRB > 50, c0 PRB ≈ 0",
                "imbalance_gap": "> 50 in both phases",
            },
            "xapp_expected_action": "control_handover (style=3 action=1) — F1 intra-gNB",
        },
    }


# ─── ES scenario ──────────────────────────────────────────────────
# 條件:5min mean PrbTotDl < 0.10 且 PdcpSduVolumeDL < 1MB
# 設計:trigger 階段 0 流量 → 觸發 ES;recovery 階段流量回升驗證解封
# 因為 ES sliding_window 是 5min,在 fast mode 下實際 wall-clock 很短就過了
def es_scenario(duration_sec: int = 80) -> dict:
    # 0~40s = trigger (no traffic), 40~60s = recovery (2 Mbps), 60~80s = idle again
    trigger_end = duration_sec * 1 // 2
    recovery_end = trigger_end + duration_sec * 1 // 4
    return {
        "scenario_id": "es_fast",
        "scene_id": SCENE_ID,
        "duration_sec": duration_sec,
        "tick_ms": TICK_MS,
        "default_serving_cell": DEFAULT_SERVING_CELL,
        "ues": [
            {
                "name": "es_ue_01",
                # 固定在 c1 附近(該 cell 在 trigger 階段是 idle)
                "positions": [
                    [0,             SOUTH_NEAR[0], SOUTH_NEAR[1], SOUTH_NEAR[2]],
                    [duration_sec,  SOUTH_NEAR[0], SOUTH_NEAR[1], SOUTH_NEAR[2]],
                ],
            },
        ],
        "traffic": [
            {
                "ue_name": "es_ue_01",
                # piecewise:trigger 期 0 / recovery 期 2000 kbps / 之後再 0
                "profile": [
                    [0,             0,     0],
                    [trigger_end,   2000, 200],
                    [recovery_end,  0,     0],
                ],
            },
        ],
        "_metadata": {
            "oai_origin": "es_traffic.sh",
            "intent": "ES (energy saving)",
            "required_topology": {
                "min_gnbs": 1, "min_cells_per_gnb": 1, "min_ues": 1,
                "rationale": "per-cell 低載判定 — 1 個 cell 就夠;HO 動作需要鄰居 cell 但不一定要 2 gNB",
            },
            "expected_kpm": {
                f"phase 0~{trigger_end}s": "RRU.PrbTotDl mean < 0.10",
                f"phase {trigger_end}~{recovery_end}s": "volume 回升 ≥ 1MB",
            },
            "xapp_expected_action": (
                "trigger: control_handover + control_slice_level_prb_quota (min=0,max=5); "
                "recovery: control_slice_level_prb_quota (min=10,max=100)"
            ),
        },
    }


# ─── 1 hr scenarios(對應 OAI 10:00-11:00 demo)──────────────────
# duration_sec=3600,多階段(讓 xApp 在 1hr 內看到多次觸發/恢復)

def im_1hr_scenario() -> dict:
    """1 hr IM:UE 沿時間在強/弱訊號區來回 → PRB 持續高、SINR 有起伏。
    對 xApp 看 PRB cap 是否反覆觸發、恢復。
    """
    return {
        "scenario_id": "im_1hr",
        "scene_id": SCENE_ID,
        "duration_sec": 3600,
        "tick_ms": TICK_MS,
        "default_serving_cell": DEFAULT_SERVING_CELL,
        "ues": [
            {
                "name": "im_ue_01",
                "positions": [
                    [0,    NORTH_FAR[0],  NORTH_FAR[1],  NORTH_FAR[2]],   # 10:00 邊緣
                    [900,  NORTH_FAR[0],  NORTH_FAR[1],  NORTH_FAR[2]],   # 10:15
                    [1200, NORTH_NEAR[0], NORTH_NEAR[1], NORTH_NEAR[2]],  # 10:20 進到近處
                    [1800, NORTH_NEAR[0], NORTH_NEAR[1], NORTH_NEAR[2]],  # 10:30
                    [2100, NORTH_FAR[0],  NORTH_FAR[1],  NORTH_FAR[2]],   # 10:35 又走遠
                    [2700, NORTH_FAR[0],  NORTH_FAR[1],  NORTH_FAR[2]],   # 10:45
                    [3000, NORTH_NEAR[0], NORTH_NEAR[1], NORTH_NEAR[2]],  # 10:50 回近
                    [3600, NORTH_NEAR[0], NORTH_NEAR[1], NORTH_NEAR[2]],  # 11:00
                ],
            },
        ],
        "traffic": [
            {"ue_name": "im_ue_01", "profile": [[0, 3000, 672]]},
        ],
        "_metadata": {
            "oai_origin": "im_traffic.sh × 40(1hr 持續壓 channel)",
            "intent": "IM (interference mitigation) — 1hr 長劇本",
            "required_topology": {
                "min_gnbs": 1, "min_cells_per_gnb": 1, "min_ues": 1,
                "rationale": "單 cell 內擁塞 — 1 UE 在 NORTH 區擺動觸發多次 PRB 滿",
            },
            "phases": "10:00-10:15 邊緣 / 10:15-10:30 近 / 10:30-10:45 邊緣 / 10:45-11:00 近",
        },
    }


def cco_1hr_scenario() -> dict:
    """1 hr CCO:UE 在 N/S 之間多次來回 → 多次 cross-cell handover 機會。
    對 xApp 看 cell imbalance 偵測 + 多次 HO 觸發。
    """
    return {
        "scenario_id": "cco_1hr",
        "scene_id": SCENE_ID,
        "duration_sec": 3600,
        "tick_ms": TICK_MS,
        "default_serving_cell": DEFAULT_SERVING_CELL,
        "ues": [
            {
                "name": "cco_ue_01",
                "positions": [
                    [0,    NORTH_NEAR[0], NORTH_NEAR[1], NORTH_NEAR[2]],  # 10:00 北
                    [600,  NORTH_NEAR[0], NORTH_NEAR[1], NORTH_NEAR[2]],  # 10:10 還在北
                    [900,  SOUTH_NEAR[0], SOUTH_NEAR[1], SOUTH_NEAR[2]],  # 10:15 到南
                    [1500, SOUTH_NEAR[0], SOUTH_NEAR[1], SOUTH_NEAR[2]],  # 10:25 還在南
                    [1800, NORTH_NEAR[0], NORTH_NEAR[1], NORTH_NEAR[2]],  # 10:30 回北
                    [2400, NORTH_NEAR[0], NORTH_NEAR[1], NORTH_NEAR[2]],  # 10:40
                    [2700, SOUTH_NEAR[0], SOUTH_NEAR[1], SOUTH_NEAR[2]],  # 10:45 到南
                    [3300, SOUTH_NEAR[0], SOUTH_NEAR[1], SOUTH_NEAR[2]],  # 10:55
                    [3600, NORTH_NEAR[0], NORTH_NEAR[1], NORTH_NEAR[2]],  # 11:00 又回北
                ],
            },
        ],
        "traffic": [
            {"ue_name": "cco_ue_01", "profile": [[0, 1500, 100]]},
        ],
        "_metadata": {
            "oai_origin": "cco_traffic.sh × 30(1hr 持續流量)",
            "intent": "CCO — UE 多次 N↔S 來回,期待 4 次以上 cross-cell HO",
            "required_topology": {
                "min_gnbs": 1, "min_cells_per_gnb": 2, "min_ues": 1,
                "rationale": "cell c0 / c1 間 handover",
            },
            "phases": "10:00-10:15 北 / 10:15-10:30 南 / 10:30-10:45 北 / 10:45-11:00 南",
        },
    }


def es_1hr_scenario() -> dict:
    """1 hr ES:idle / recovery 多階段交替 → 看 xApp 多次 cap+解封 cycle。"""
    return {
        "scenario_id": "es_1hr",
        "scene_id": SCENE_ID,
        "duration_sec": 3600,
        "tick_ms": TICK_MS,
        "default_serving_cell": DEFAULT_SERVING_CELL,
        "ues": [
            {
                "name": "es_ue_01",
                "positions": [
                    [0,    SOUTH_NEAR[0], SOUTH_NEAR[1], SOUTH_NEAR[2]],
                    [3600, SOUTH_NEAR[0], SOUTH_NEAR[1], SOUTH_NEAR[2]],
                ],
            },
        ],
        "traffic": [
            {
                "ue_name": "es_ue_01",
                # 4 個 cycle:idle 12 min → 5 min recovery,反覆
                "profile": [
                    [0,    0,    0],       # 10:00 idle 開始
                    [720,  2000, 200],     # 10:12 recovery 1
                    [1020, 0,    0],       # 10:17 回 idle
                    [1620, 2000, 200],     # 10:27 recovery 2
                    [1920, 0,    0],       # 10:32 idle
                    [2520, 1500, 150],     # 10:42 recovery 3(較小流量)
                    [2820, 0,    0],       # 10:47 idle
                    [3420, 2500, 250],     # 10:57 recovery 4
                    [3600, 0,    0],       # 11:00 結束
                ],
            },
        ],
        "_metadata": {
            "oai_origin": "es_traffic.sh × 多 cycle(1hr)",
            "intent": "ES — 4 個 idle/recovery cycle,期待 xApp 多次 cap → 解封",
            "required_topology": {
                "min_gnbs": 1, "min_cells_per_gnb": 1, "min_ues": 1,
                "rationale": "per-cell 低載 → 流量分段觸發",
            },
            "phases": "10:00 開始 idle,每 ~17 min 一個 recovery burst,共 4 cycle",
        },
    }


def main():
    scenarios = [
        ("im_fast.json", im_scenario()),
        ("cco_fast.json", cco_scenario()),
        ("es_fast.json", es_scenario()),
        ("im_1hr.json", im_1hr_scenario()),
        ("cco_1hr.json", cco_1hr_scenario()),
        ("es_1hr.json", es_1hr_scenario()),
    ]
    for fname, sc in scenarios:
        # 所有劇本共用 BASE_GNBS 拓樸(1 gNB 2 cells)。
        # buildings 預設 BASE_BUILDINGS([]) — 全劇本起跑時不覆寫 Omniverse DB
        # 既有建築。要在劇本層級加,在個別 scenario 函式 return 的 dict 塞 buildings。
        sc.setdefault("gnbs", BASE_GNBS)
        sc.setdefault("buildings", BASE_BUILDINGS)
        out = OUT_DIR / fname
        with open(out, "w", encoding="utf-8") as f:
            json.dump(sc, f, indent=2, ensure_ascii=False)
        ticks = int(sc["duration_sec"] * 1000 / sc["tick_ms"])
        print(
            f"  ✓ {fname}: id={sc['scenario_id']} ues={len(sc['ues'])} "
            f"duration={sc['duration_sec']}s ticks={ticks} "
            f"→ intent={sc['_metadata']['intent']}"
        )
    print()
    print(f"OK → {OUT_DIR}/{{im,cco,es}}_fast.json")
    print()
    print("上傳給 Omniverse:")
    print("  for f in im cco es; do")
    print('    curl -XPOST http://localhost:8001/api/v0.1/RAN/Scenario/ScenarioController/upload \\')
    print(f'      -H "Content-Type: application/json" --data-binary @{OUT_DIR}/${{f}}_fast.json')
    print("  done")
    print()
    print("跑 fast run(scenario_id 任選):")
    print("  curl -XPOST http://localhost:8104/api/v0.1/Physics/Precompute/run -d '{\"scenario_id\":\"im_fast\"}'")


if __name__ == "__main__":
    main()
