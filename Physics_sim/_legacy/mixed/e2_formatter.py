"""把 sionna_engine 的 path_gain_linear 轉成 E2-like JSON（對齊 RAN_knowledge/E2.md 格式）+ 扁平 ue_status。"""
import math
from typing import Any

from main.apps.ran_signal.services.optional.ran_calculation.mcs_table import (
    mcs_to_throughput_mbps,
    sinr_to_mcs,
)
from main.apps.ran_signal.services.optional.ran_calculation.mimo_processor import compute_mimo
from main.utils.env_loader import get_bool, get_float
from main.utils.logger import get_logger

logger = get_logger(__name__)


# Boltzmann * 290 K 換成 dBm: -174 dBm/Hz
THERMAL_NOISE_DBM_PER_HZ = -174.0


def _lin_to_db(x: float) -> float:
    return 10.0 * math.log10(x) if x > 0 else -999.0


def _db_to_lin(x: float) -> float:
    return 10.0 ** (x / 10.0)


def _quality_label(sinr_db: float) -> str:
    if sinr_db >= 20:
        return "excellent"
    if sinr_db >= 10:
        return "good"
    if sinr_db >= 0:
        return "fair"
    return "poor"


def build(
    *,
    timestamp_ms: int,
    gnbs: list[dict[str, Any]],
    ue_positions: list[dict[str, Any]],
    cir_result: dict[str, Any],
    pf_scheduler: Any = None,     # 可選；None → 退化成每 UE 拿滿 PRB
    mcs_controller: Any = None,   # 可選；None → 退化成查表 MCS（無閉環）
    serving_cells: dict[str, str] | None = None,  # Sionna 的 serving gNB（可選）
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """輸出 (e2_entries, ue_status, warnings)."""
    noise_figure_db = get_float("SIM_NOISE_FIGURE_DB", default=7.0)
    enable_mimo_capacity = get_bool("ENABLE_MIMO_CAPACITY", default=True)
    path_gain = cir_result["path_gain_linear"]  # {ue_id: {gnb_name: pg_linear}}
    channel_matrix = cir_result.get("channel_matrix") or {}  # {ue_id: {gnb_name: H}}

    # 為缺少 pci/cell_id 的 gNBs 分配預設值（從 cells 優先，無則用 index）
    for idx, gnb in enumerate(gnbs):
        cells = gnb.get("cells") or []
        if "pci" not in gnb:
            gnb["pci"] = int(cells[0]["pci"]) if cells else idx
        if "cell_id" not in gnb:
            gnb["cell_id"] = f"cell_{gnb['pci']}"

    # gNB 查表
    gnb_by_name = {g["name"]: g for g in gnbs}

    warnings: list[str] = []

    # 第一輪：為每個 UE 算對所有 gNB 的 RSRP + pick serving
    per_ue_rsrp: dict[str, dict[str, float]] = {}  # ue_id -> {gnb_name: rsrp_dbm}
    per_ue_serving: dict[str, str] = {}            # ue_id -> serving_gnb_name

    for ue in ue_positions:
        ue_id = ue["id"]
        if ue_id not in path_gain:
            warnings.append(f"ue '{ue_id}' not in CIR result")
            continue

        rsrp_map: dict[str, float] = {}
        for gnb in gnbs:
            pg = path_gain[ue_id].get(gnb["name"], 0.0)
            rsrp = float(gnb["power_dbm"]) + _lin_to_db(pg)
            rsrp_map[gnb["name"]] = rsrp

        if not rsrp_map:
            warnings.append(f"ue '{ue_id}' has no gNB path gain")
            continue

        serving = max(rsrp_map, key=rsrp_map.get)  # type: ignore[arg-type]
        per_ue_rsrp[ue_id] = rsrp_map
        per_ue_serving[ue_id] = serving

    # ── 中間輪：算每 UE SINR + 按 serving gNB 做 PF scheduling ─────
    # 先把所有 UE 的 SINR 算出來（因為 PF scheduler 要用它推 rate）
    per_ue_sinr: dict[str, float] = {}
    per_ue_sinr_lin: dict[str, float] = {}
    per_ue_nprb_max: dict[str, int] = {}   # 該 UE serving gNB 的 PRB 總數
    per_ue_bw_hz: dict[str, float] = {}

    for ue_id, serving_name in per_ue_serving.items():
        serving_gnb = gnb_by_name[serving_name]
        rsrp_map = per_ue_rsrp[ue_id]
        rsrp_serving = rsrp_map[serving_name]
        bw_hz = float(serving_gnb["bandwidth_mhz"]) * 1e6
        noise_dbm = THERMAL_NOISE_DBM_PER_HZ + 10.0 * math.log10(bw_hz) + noise_figure_db
        noise_lin = _db_to_lin(noise_dbm)
        interf_lin = sum(
            _db_to_lin(r) for name, r in rsrp_map.items() if name != serving_name
        )
        sinr_lin = _db_to_lin(rsrp_serving) / max(interf_lin + noise_lin, 1e-20)
        per_ue_sinr[ue_id] = 10.0 * math.log10(sinr_lin)
        per_ue_sinr_lin[ue_id] = sinr_lin
        per_ue_nprb_max[ue_id] = max(1, int(bw_hz / (12 * 30e3)))
        per_ue_bw_hz[ue_id] = bw_hz

    # 按 serving gNB 分組，呼叫 PF scheduler 分配 PRB
    rb_alloc_by_ue: dict[str, int] = {}
    if pf_scheduler is not None:
        ues_grouped_by_gnb: dict[str, list[dict[str, Any]]] = {}
        for ue_id, serving_name in per_ue_serving.items():
            ues_grouped_by_gnb.setdefault(serving_name, []).append({
                "id": ue_id,
                "sinr_db": per_ue_sinr[ue_id],
            })
        for gnb_name, ues_on_gnb in ues_grouped_by_gnb.items():
            # 取該 gNB 的 PRB 總數（假設同 gNB 的 UE 都用同 bw）
            n_prb = per_ue_nprb_max[ues_on_gnb[0]["id"]]
            alloc = pf_scheduler.allocate(
                gnb_name=gnb_name,
                ues_on_gnb=ues_on_gnb,
                n_prb_total=n_prb,
            )
            rb_alloc_by_ue.update(alloc)
    else:
        # 無 scheduler → 退化：每 UE 拿滿（舊行為）
        rb_alloc_by_ue = dict(per_ue_nprb_max)

    # 第二輪：用 PF 分到的 PRB 算 throughput / MCS / 組 ue_entry
    grouped: dict[str, list[dict[str, Any]]] = {g["name"]: [] for g in gnbs}
    ue_status_list: list[dict[str, Any]] = []

    for ue in ue_positions:
        ue_id = ue["id"]
        if ue_id not in per_ue_serving:
            continue

        serving_name = per_ue_serving[ue_id]
        serving_gnb = gnb_by_name[serving_name]

        # 選 serving cell：若 gNB 有多個 cells，用位置方位角選最接近的 cell
        gnb_cells = serving_gnb.get("cells") or []
        if len(gnb_cells) > 1 and "position" in serving_gnb:
            # 計算 UE 相對 gNB 的方位角（horizontal plane）
            gx, gy = serving_gnb["position"][0], serving_gnb["position"][2]
            ux, uy = ue["position"][0], ue["position"][2]
            ue_angle = (math.degrees(math.atan2(uy - gy, ux - gx)) + 360) % 360

            # 找最接近的 cell sector（角度距離最小）
            def angle_distance(target: float, source: float) -> float:
                diff = abs(target - source)
                return min(diff, 360 - diff)

            best_cell = min(gnb_cells, key=lambda c: angle_distance(ue_angle, c.get("azimuth_deg", 0)))
            serving_pci = int(best_cell["pci"])
            serving_cell_id = f"cell_{best_cell['pci']}"

            # DEBUG: 輸出角度計算和 cell 選擇過程
            cell_distances = [(c["pci"], c.get("azimuth_deg", 0), angle_distance(ue_angle, c.get("azimuth_deg", 0))) for c in gnb_cells]
            logger.info(
                "[CellSelection] UE=%s gnb=%s pos=[%.1f,%.1f] gpos=[%.1f,%.1f] ue_angle=%.1f° cells=%s → selected_pci=%d",
                ue_id, serving_name, ux, uy, gx, gy, ue_angle,
                [(p, az, d) for p, az, d in cell_distances], serving_pci
            )
        elif gnb_cells:
            serving_pci = int(gnb_cells[0]["pci"])
            serving_cell_id = f"cell_{gnb_cells[0]['pci']}"
        else:
            serving_pci = int(serving_gnb["pci"])
            serving_cell_id = str(serving_gnb.get("cell_id", f"cell_{serving_gnb['pci']}"))

        rsrp_map = per_ue_rsrp[ue_id]
        rsrp_serving = rsrp_map[serving_name]

        bw_hz = per_ue_bw_hz[ue_id]
        noise_dbm = THERMAL_NOISE_DBM_PER_HZ + 10.0 * math.log10(bw_hz) + noise_figure_db
        noise_lin = _db_to_lin(noise_dbm)
        interf_lin = sum(
            _db_to_lin(r) for name, r in rsrp_map.items() if name != serving_name
        )
        sinr_lin = per_ue_sinr_lin[ue_id]
        sinr_db = per_ue_sinr[ue_id]

        # RSRQ — 3GPP 簡化
        rsrq_db = -10.0 * math.log10(12.0) - 10.0 * math.log10(1.0 + 1.0 / max(sinr_lin, 1e-6))
        rsrq_db = max(rsrq_db, -43.0)

        # ★ MCS：若有 controller 走閉環；否則退化查表
        allocated_rb = rb_alloc_by_ue.get(ue_id, per_ue_nprb_max[ue_id])
        if mcs_controller is not None:
            mcs, _bler = mcs_controller.update(ue_id, sinr_db, timestamp_ms)
            # 由 MCS 反推 bps_re
            from main.apps.ran_signal.services.optional.ran_calculation.mcs_table import _SINR_TO_MCS
            bps_re_lookup = {row[1]: row[2] for row in _SINR_TO_MCS}
            # 找最接近的 bps_re
            bps_re = bps_re_lookup.get(mcs, 0)
            if bps_re == 0:
                # mcs 不在 table 裡，用 sinr_to_mcs 查
                _, bps_re = sinr_to_mcs(sinr_db)
        else:
            mcs, bps_re = sinr_to_mcs(sinr_db)
        dl_tput_single = mcs_to_throughput_mbps(mcs=mcs, bps_re=bps_re, n_rb=allocated_rb)

        # ★ MIMO multi-stream：若有 channel matrix 就跑 SVD-based capacity，
        #   否則 fallback 到單 stream（dl_tput = dl_tput_single）
        ue_h_map = channel_matrix.get(ue_id, {})
        H_serving = ue_h_map.get(serving_name)
        mimo_rank = 1
        per_stream_sinr_db: list[float] = [sinr_db]
        per_stream_mcs: list[int] = [int(mcs)]
        if enable_mimo_capacity and H_serving is not None and H_serving.size > 0:
            tx_power_lin = _db_to_lin(float(serving_gnb["power_dbm"]))
            mimo_res = compute_mimo(
                H_serving,
                tx_power_lin=tx_power_lin,
                noise_power_lin=noise_lin + interf_lin,
            )
            if mimo_res.rank > 0:
                mimo_rank = mimo_res.rank
                per_stream_sinr_db = list(mimo_res.per_stream_sinr_db)
                # 對每 stream 各自查 MCS 表，加總成 multi-stream 吞吐率
                stream_tputs: list[float] = []
                per_stream_mcs = []
                for s_sinr_db in per_stream_sinr_db:
                    s_mcs, s_bps_re = sinr_to_mcs(s_sinr_db)
                    per_stream_mcs.append(int(s_mcs))
                    stream_tputs.append(
                        mcs_to_throughput_mbps(mcs=s_mcs, bps_re=s_bps_re, n_rb=allocated_rb)
                    )
                dl_tput = sum(stream_tputs)
            else:
                dl_tput = dl_tput_single
        else:
            dl_tput = dl_tput_single
        # UL：reciprocity 近似，功率差 23 dB，NF 差 4 dB ≈ SINR 低 19 dB
        ul_sinr_db = sinr_db - 19.0
        ul_mcs, ul_bps_re = sinr_to_mcs(ul_sinr_db)
        # UL PRB 粗估 = DL 分配的一半（TDD 4:1 近似 + UL 排程通常較保守）
        ul_rb = max(1, allocated_rb // 2)
        ul_tput = mcs_to_throughput_mbps(mcs=ul_mcs, bps_re=ul_bps_re, n_rb=ul_rb)

        n_rb = allocated_rb   # 用實際分配的 PRB

        # neighbors：只保留 RSRP > serving - 20 dB 的鄰 gNB
        neighbors = []
        interfered_flag = 0
        for name, r in rsrp_map.items():
            if name == serving_name:
                continue
            if r > rsrp_serving - 20:
                g_nb = gnb_by_name[name]
                # neighbor 的 RSRQ：以該 neighbor 為 serving 重算同樣公式
                neigh_signal_lin = _db_to_lin(r)
                neigh_interf_lin = sum(
                    _db_to_lin(rr) for nn, rr in rsrp_map.items() if nn != name
                )
                neigh_sinr_lin = neigh_signal_lin / max(neigh_interf_lin + noise_lin, 1e-20)
                neigh_rsrq = -10.0 * math.log10(12.0) - 10.0 * math.log10(1.0 + 1.0 / max(neigh_sinr_lin, 1e-6))
                neigh_rsrq = max(neigh_rsrq, -43.0)
                neighbors.append({
                    g_nb["cell_id"]: {
                        "rsrp": int(round(r)),
                        "rsrq": int(round(neigh_rsrq)),
                    }
                })
                if r > rsrp_serving - 6:
                    interfered_flag = 1

        # UE 的 role / qos_5qi 從 input 來（有預設）
        ue_role = int(ue.get("role", 1))
        ue_qos = int(ue.get("qos_5qi", 9))

        ue_entry = {
            "role": ue_role,
            "ue_id": ue_id,
            "interfered": interfered_flag,
            "rsrp": int(round(rsrp_serving)),
            "rsrq": int(round(rsrq_db)),
            "sinr": int(round(sinr_db)),
            "neighbors": neighbors,
            "dl_throughput": dl_tput,
            "ul_throughput": ul_tput,
            "rb_start": 0,
            "rb_width": n_rb,
        }
        grouped[serving_name].append(ue_entry)

        ue_status_list.append({
            "ue_id": ue_id,
            "position": list(ue["position"]),
            "serving_gnb": serving_name,
            "serving_pci": serving_pci,
            "serving_cell_id": serving_cell_id,
            "rsrp_dbm": round(rsrp_serving, 1),
            "sinr_db": round(sinr_db, 1),
            "all_rsrp": {name: round(r, 1) for name, r in rsrp_map.items()},
            "throughput_dl_mbps": dl_tput,
            "throughput_ul_mbps": ul_tput,
            "quality": _quality_label(sinr_db),
            "qos_5qi": ue_qos,
            "role": ue_role,
            "mcs_dl": int(mcs),
            "rb_width_dl": int(allocated_rb),
            "mimo_rank": int(mimo_rank),
            "mimo_streams_sinr_db": [round(float(x), 1) for x in per_stream_sinr_db],
            "mimo_streams_mcs": list(per_stream_mcs),
        })

    # 組 E2 entries（一個 gNB 一個 entry，即使沒 UE 也列出以對齊 E2.md 格式）
    e2_entries: list[dict[str, Any]] = []
    ts_sec = timestamp_ms // 1000
    for gnb in gnbs:
        entry = {
            "gnb_id": str(gnb["pci"]),
            "timestamp": ts_sec,
            "cells": [{
                "cell_id": str(gnb["cell_id"]),
                "ran_name": gnb["name"],
                "pci": int(gnb["pci"]),
                "ues": grouped.get(gnb["name"], []),
            }],
        }
        e2_entries.append(entry)

    return e2_entries, ue_status_list, warnings
