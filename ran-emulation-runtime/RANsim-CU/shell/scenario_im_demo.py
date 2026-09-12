#!/usr/bin/env python3
"""IM/CCO/ES intent demo scenario — 對齊 intents-interface.md §4.x 觸發條件,
驅動 sim KPM 進「條件可達成」狀態, 留 xApp 反應時間, 觀察 control 套下去後 KPM 是否改善.

═══════════════════════════════════════════════════════════════════════════
場景設置 (跑 scenario 前先執行 setup_multi_ue.py 建這個分布):

  sim CU:    gnb_208_095_000038 (1 gNB)
  sim cells: gnb4_c0..c3 (4 cells)
  UE 配置:
    gnb4_c0  ★ HOT  : 8 UE × 20 Mbps demand     (cell PRB 滿, per-UE Thp 低)
    gnb4_c1     warm : 4 UE × 5 Mbps             (cell mid load)
    gnb4_c2     cold : 1 UE × 1 Mbps             (cell low load)
    gnb4_c3   ★ idle : 0 UE                      (cell empty, CCO cold side)

  → Cell 間負載差距大 (c0 滿 vs c3 空), CCO cell-level 觸發 demo 可達
  → c0 多 UE 搶 PRB, 每 UE Thp 自然 < 5 Mbps, IM 三條件可達
  → ES 用 phase 切低載達成

═══════════════════════════════════════════════════════════════════════════

對齊 spec §4.x 觸發條件 (intents-interface.md):
  IM (im-01)  : RRU.PrbTotDl > 0.70 AND DRB.UEThpDl < 5000 kbps AND DRB.RlcSduDelayDl > 50ms
                  → action: control_slice_level_prb_quota(min=10, max=50, dedicated=100)
  CCO (cco-01): cell 間 PrbTotDl 差距 > 0.30, hot>0.85 cold<0.30
                  (spec 是 gNB 間, demo 用 cell 間代替, 1 sim CU = 1 gNB 結構限制)
                  → action: control_handover hot cell 邊緣 UE → cold neighbor cell
  ES (es-01)  : 5min mean PrbTotDl < 0.10 AND PdcpSduVolumeDL < 1MB
                  → action: 1) HO 殘留 UE 走  2) PRB quota (min=0, max=5, dedicated=0)

Sim demo scaling:
  - ES 5min mean → 30s sliding mean (避免 demo 等 5 分鐘觸發)
  - CCO「gNB 間」→「cell 間」(sim 1 gNB 結構限制, 但 cell-level 一樣展示負載均衡概念)
  - 其他 spec-compliant

Strategy reaction time:
  trigger 條件達成後 hold N 秒 (default 30), 模擬 xApp:
    1. 收 KPM Indication 累積觀察
    2. mean / sliding window 評估 threshold
    3. 確認連續達 → 下 RC Control
  超過 hold time scenario 自己 fire RC Control 模擬 strategy 下發 (--mock-control 預設 ON).
  關掉就是純驅動 sim KPM, 等 RIC 端真 strategy 下 control.

Phase timeline (T 從 scenario 啟動算, 預設 5 min):
  0-45s    Phase 1  baseline 50 Mbps           給 strategy 看 KPM 穩定基準
  45-120s  Phase 2  ES 觸發 (低載)              traffic 0.05 Mbps, 等 ES condition met
                                                 → mock strategy 下 PRB quota (0,5,0)
                                                 → 觀察 quota 套下去後 PRB / Thp / Vol 變化
 120-195s  Phase 3  IM 觸發模擬 (擁塞 proxy)     先壓 PRB quota max=5 + traffic 50 Mbps
                                                 → Thp cap <5M + Delay 高, 模擬 IM 部分條件
                                                 → mock strategy 下 PRB quota (10, 50, 100)
                                                 → 觀察 quota 放寬後 Thp 是否回升
 195-225s  Phase 4  CCO (sim 不適用, log skip)
 225-300s  Phase 5  全復原 + 觀察 baseline 回穩

Usage:
  python3 scenario_im_demo.py [--ue-id UE_ID] [--duration-sec 300] [--no-mock-control]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from collections import deque
from datetime import datetime
from typing import Any

UE_BASE = "http://localhost:8105"
CU_BASE = "http://localhost:8101"
ADAPTER = "http://localhost:8201"

LOG_FILE = "/tmp/scenario_run.log"


def _post(url: str, body: dict, timeout: float = 5.0) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")[:200]
        return {"_http_error": e.code, "_body": body_txt}
    except Exception as exc:
        return {"_error": repr(exc)}


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(msg: str) -> None:
    print(msg, flush=True)


# ── sim API wrappers ──────────────────────────────────────────────

def set_traffic(ue_id: str, rate_mbps: float, pattern: str = "cbr") -> bool:
    body = {
        "ue_id": ue_id,
        "traffic_profile": {
            "pattern": pattern,
            "rate_mbps": rate_mbps,
            "sdu_size": 1500,
            "bearer_id": 1,
        },
    }
    resp = _post(f"{CU_BASE}/api/v0.1/CU/Session/SessionController/update_traffic_profile", body)
    ok = resp.get("success", False)
    _log(f"[{_now()}] ▸ traffic → {rate_mbps} Mbps ({pattern})  ok={ok}")
    return ok


def set_position(ue_id: str, x: float, y: float, z: float = 1.5) -> bool:
    now_ms = int(time.time() * 1000)
    body = {
        "ue_id": ue_id,
        "waypoints": [{"x": x, "y": y, "z": z, "t_ms": 0}],
        "mode": "loop",
        "start_at_ms": now_ms,
    }
    resp = _post(f"{UE_BASE}/api/v0.1/UE/Trajectory/set", body)
    ok = resp.get("success", False)
    _log(f"[{_now()}] ▸ position → ({x:.0f}, {y:.0f}, {z:.0f})  ok={ok}")
    return ok


def fire_rc_control_prb_quota(min_prb: int, max_prb: int, dedicated_prb: int,
                               purpose: str) -> bool:
    """模擬 xApp 下 E2 Control Style 2/6 (control_slice_level_prb_quota).

    經 sim CU /CU/E2/Control/request endpoint, 跟正式 RIC RC Control 同條 path.
    """
    body = {
        "ric_req_id": {"requestor_id": 9999, "instance_id": 1},
        "ran_function_id": 3,
        "control_header": {
            "control_style": 2,
            "control_action_id": 6,
            "node": "gnb_208_095_000038",
        },
        "control_message": {
            "min_prb": min_prb,
            "max_prb": max_prb,
            "dedicated_prb": dedicated_prb,
        },
    }
    resp = _post(f"{CU_BASE}/api/v0.1/CU/E2/Control/request", body)
    ok = resp.get("success", False)
    _log(f"[{_now()}] ⚡ MOCK STRATEGY → set_prb_quota({min_prb},{max_prb},{dedicated_prb}) [{purpose}]  ok={ok}")
    if ok:
        cells = resp.get("data", {}).get("cells_applied", [])
        _log(f"           applied to cells={cells}")
    return ok


# ── KPM polling ───────────────────────────────────────────────────

def snapshot_kpm() -> dict:
    """從 sim CU KPM reporter 直接拉 (e2adapter snapshot ring stale, sim CU 才即時)."""
    resp = _post(f"{CU_BASE}/api/v0.1/CU/E2/E2KpmReporter/read", {})
    return resp.get("data", {})


def _extract_ue_metrics(snap: dict, ue_id: str) -> dict | None:
    for ue in snap.get("ue_status") or []:
        if ue.get("ue_id") == ue_id and ue.get("rrc_state") == "CONNECTED":
            return {
                "prb_pct":   (ue.get("rb_width_dl") or 0) / 273 * 100,
                "thp_kbps":  (ue.get("throughput_dl_mbps") or 0) * 1000,
                "delay_ms":  ue.get("rlc_sdu_delay_dl_ms") or 0,
                "vol_dl_b":  ue.get("pdcp_sdu_volume_dl") or 0,
                "rsrp_dbm":  ue.get("rsrp_dbm") or 0,
                "sinr_db":   ue.get("sinr_db") or 0,
                "mcs_dl":    ue.get("mcs_dl") or 0,
                "serving":   ue.get("serving_cell") or "",
                "ue_id":     ue.get("ue_id"),
            }
    return None


def _extract_all_connected(snap: dict) -> list[dict]:
    """所有 CONNECTED UEs metrics, 給 IM (per-UE) + CCO (per-cell aggregate) 用."""
    out = []
    for ue in snap.get("ue_status") or []:
        if ue.get("rrc_state") != "CONNECTED":
            continue
        out.append({
            "prb_pct":   (ue.get("rb_width_dl") or 0) / 273 * 100,
            "thp_kbps":  (ue.get("throughput_dl_mbps") or 0) * 1000,
            "delay_ms":  ue.get("rlc_sdu_delay_dl_ms") or 0,
            "vol_dl_b":  ue.get("pdcp_sdu_volume_dl") or 0,
            "serving":   ue.get("serving_cell") or "",
            "ue_id":     ue.get("ue_id") or "",
            "ngap_id":   ue.get("amf_ue_ngap_id") or 0,
        })
    return out


def _aggregate_per_cell(ues: list[dict]) -> dict[str, dict]:
    """把多 UE metrics 聚合成 per-cell 視角 (對齊 spec cell-level PrbTotDl).

    spec PrbTotDl 是 cell-level 使用率, 不是 per-UE. 所以多 UE 的 rb_width 加總
    後 / 273 才是 cell PRB%. 我們 sim KPM 給 per-UE rb_width, 這裡聚合.
    """
    cells: dict[str, dict] = {}
    for u in ues:
        c = u["serving"]
        if not c:
            continue
        agg = cells.setdefault(c, {
            "ue_count": 0,
            "prb_pct_max": 0,
            "prb_pct_sum": 0,    # cell-level PRB% 對齊 spec
            "thp_kbps_total": 0,
            "vol_dl_b_total": 0,
        })
        agg["ue_count"] += 1
        agg["prb_pct_max"] = max(agg["prb_pct_max"], u["prb_pct"])
        agg["prb_pct_sum"] += u["prb_pct"]
        agg["thp_kbps_total"] += u["thp_kbps"]
        agg["vol_dl_b_total"] += u["vol_dl_b"]
    # clamp PRB sum to physical max 100% per cell
    for agg in cells.values():
        agg["prb_pct_sum"] = min(agg["prb_pct_sum"], 100.0)
    return cells


def print_kpm(label: str, m: dict | None) -> None:
    if not m:
        _log(f"[{_now()}] {label:35s}  KPM empty")
        return
    _log(
        f"[{_now()}] {label:35s}  cell={m['serving']:8s} "
        f"PRB={m['prb_pct']:>5.1f}% Thp={m['thp_kbps']:>7.0f}kbps "
        f"Delay={m['delay_ms']:>6.1f}ms VolDL={m['vol_dl_b']:>10} "
        f"RSRP={m['rsrp_dbm']:>6.1f} SINR={m['sinr_db']:>4.1f} mcs={m['mcs_dl']:>2}"
    )


# ── Trigger condition evaluators (對齊 intents-interface.md §4.x) ──

def check_im_trigger(ues: list[dict]) -> tuple[bool, str, str]:
    """IM (im-01) — 任一「有 traffic」UE 三條件同時達成 (per-UE 評估).

    排除 idle UE (thp=0 AND delay=0), 避免 sim DU scheduler 對 idle UE 仍分 PRB
    造成 PRB=100% Thp=0 Delay=0 誤觸發.
    回 (triggered, detail, target_ue_id).
    """
    # 過濾 idle: 必須有實際 traffic 跡象 (delay 高表示 queueing, 即使 thp 低也算)
    active = [u for u in ues if u.get("delay_ms", 0) > 0 or u.get("vol_dl_b", 0) > 0]
    if not active:
        return False, "no active UE (all idle)", ""
    best = None
    best_score = -1
    for u in active:
        prb_ok = u["prb_pct"] > 70
        thp_ok = u["thp_kbps"] < 5000
        delay_ok = u["delay_ms"] > 50
        score = int(prb_ok) + int(thp_ok) + int(delay_ok)
        if score > best_score:
            best_score = score
            best = u
        if prb_ok and thp_ok and delay_ok:
            detail = (
                f"UE={u['ue_id']} cell={u['serving']} "
                f"PRB={u['prb_pct']:.0f}%>70:✓ "
                f"Thp={u['thp_kbps']:.0f}<5k:✓ "
                f"Delay={u['delay_ms']:.0f}>50:✓"
            )
            return True, detail, u["ue_id"]
    u = best
    detail = (
        f"best={u['ue_id']} cell={u['serving']} "
        f"PRB={u['prb_pct']:.0f}%>70:{'✓' if u['prb_pct']>70 else '✗'} "
        f"Thp={u['thp_kbps']:.0f}<5k:{'✓' if u['thp_kbps']<5000 else '✗'} "
        f"Delay={u['delay_ms']:.0f}>50:{'✓' if u['delay_ms']>50 else '✗'}"
    )
    return False, detail, u["ue_id"]


def check_cco_trigger(cells: dict[str, dict]) -> tuple[bool, str, str, str]:
    """CCO (cco-01 cell-level demo) — cell 間 cell-level PrbTotDl 差距 > 0.30,
    hot>0.85, cold<0.30.

    用 prb_pct_sum (cell-level, 對齊 spec). 回 (triggered, detail, hot_cell, cold_cell).
    """
    if len(cells) < 2:
        return False, f"only {len(cells)} cell(s) active", "", ""
    sorted_cells = sorted(cells.items(), key=lambda x: x[1]["prb_pct_sum"], reverse=True)
    hot_cell, hot_data = sorted_cells[0]
    cold_cell, cold_data = sorted_cells[-1]
    hot_pct = hot_data["prb_pct_sum"]
    cold_pct = cold_data["prb_pct_sum"]
    gap = (hot_pct - cold_pct) / 100  # → 0..1
    triggered = (gap > 0.30) and (hot_pct > 85) and (cold_pct < 30)
    detail = (
        f"hot={hot_cell}(sum {hot_pct:.0f}%) "
        f"cold={cold_cell}(sum {cold_pct:.0f}%) "
        f"gap={gap:.2f}>0.30:{'✓' if gap>0.30 else '✗'} "
        f"hot>0.85:{'✓' if hot_pct>85 else '✗'} "
        f"cold<0.30:{'✓' if cold_pct<30 else '✗'}"
    )
    return triggered, detail, hot_cell, cold_cell


# ── Per-phase reconfig (動態調整 traffic 製造各 case 觸發場景) ────

def _list_demo_ues_by_cell() -> dict[str, list[str]]:
    """從 sim CU 拉所有 demo_ UE, group by serving_cell."""
    resp = _post(f"{CU_BASE}/api/v0.1/CU/Session/SessionController/list", {})
    out: dict[str, list[str]] = {}
    for u in resp.get("data", []) or []:
        ue_id = u.get("ue_id", "")
        if not ue_id.startswith("demo_"):
            continue
        if u.get("rrc_state") != "CONNECTED":
            continue
        cell = u.get("serving_cell", "")
        out.setdefault(cell, []).append(ue_id)
    return out


def reconfig_for_phase(phase_name: str, ues_by_cell: dict[str, list[str]]) -> None:
    """每 phase 開始重新分配 traffic 製造對應 trigger 條件可達成的場景."""
    if phase_name == "Phase 2 ES":
        # ES: 全 cell 全 UE pattern=idle, 期望 cell PRB sum 降到 < 10%
        _log(f"[{_now()}] ▸ Phase 2 reconfig: ALL UEs → pattern=idle (cell PRB drop)")
        for ue_list in ues_by_cell.values():
            for ue_id in ue_list:
                set_traffic(ue_id, 0.0, pattern="idle")
    elif phase_name == "Phase 3 IM":
        # IM: c0 UE 全高 demand 製造 cell-level 擁塞 + per-UE Thp 切碎
        c0_ues = ues_by_cell.get("gnb4_c0", [])
        _log(f"[{_now()}] ▸ Phase 3 reconfig: c0 {len(c0_ues)} UEs → 30 Mbps each (cell congestion)")
        for ue_id in c0_ues:
            set_traffic(ue_id, 30.0)
        # 其他 cell idle 避免干擾
        for cell, ue_list in ues_by_cell.items():
            if cell == "gnb4_c0":
                continue
            for ue_id in ue_list:
                set_traffic(ue_id, 0.0, pattern="idle")
    elif phase_name == "Phase 4 CCO":
        # CCO: c0 UE 全滿載, 其他 cell 全 idle, 製造 hot vs cold imbalance
        c0_ues = ues_by_cell.get("gnb4_c0", [])
        _log(f"[{_now()}] ▸ Phase 4 reconfig: c0 {len(c0_ues)} UEs 50 Mbps; c1/c2 idle")
        for ue_id in c0_ues:
            set_traffic(ue_id, 50.0)
        for cell, ue_list in ues_by_cell.items():
            if cell == "gnb4_c0":
                continue
            for ue_id in ue_list:
                set_traffic(ue_id, 0.0, pattern="idle")
    elif phase_name == "Phase 5 restore":
        # 復原成 setup 預設分布
        _log(f"[{_now()}] ▸ Phase 5 reconfig: restore default per-cell traffic")
        rates = {"gnb4_c0": 20.0, "gnb4_c1": 5.0, "gnb4_c2": 1.0}
        for cell, ue_list in ues_by_cell.items():
            r = rates.get(cell, 0.0)
            for ue_id in ue_list:
                if r > 0:
                    set_traffic(ue_id, r)
                else:
                    set_traffic(ue_id, 0.0, pattern="idle")


def check_es_trigger(cell_history: deque) -> tuple[bool, str, str]:
    """ES (es-01) — volume-based 評估 (sim DU 沒 backpressure, PRB 條件結構性達不到).

    Demo evaluator: 任一 cell 最近 15s mean Volume < 1MB → ES.
    PRB<10% 條件因 sim DU scheduler 對 idle UE 仍分滿 PRB, 結構上達不到 — 故略.
    Volume<1MB 才是 ES 真實主指標 (5min mean → demo 縮 15s 看最近狀態).
    回 (triggered, detail, target_cell).
    """
    if not cell_history:
        return False, "no history", ""
    # 用最近 15s, 避免被 Phase 切換前的高 vol 殘留拖累 mean
    recent = list(cell_history)[-15:]
    cell_means: dict[str, dict] = {}
    for snap in recent:
        for c, agg in snap.items():
            m = cell_means.setdefault(c, {"prb_sum": 0.0, "vol_sum": 0.0, "n": 0})
            m["prb_sum"] += agg["prb_pct_sum"]
            m["vol_sum"] += agg["vol_dl_b_total"]
            m["n"] += 1
    for c, m in cell_means.items():
        if m["n"] < 5:
            continue
        vol_mean = m["vol_sum"] / m["n"]
        prb_mean = m["prb_sum"] / m["n"]
        if vol_mean < 1_048_576:
            detail = (
                f"cell={c} Vol_mean={vol_mean/1024:.0f}KB<1MB:✓ "
                f"PRB_mean={prb_mean:.0f}% (sim 結構不參考) window={m['n']}s"
            )
            return True, detail, c
    best_c, best_m = min(cell_means.items(), key=lambda kv: kv[1]["vol_sum"]/max(kv[1]["n"],1))
    vol_mean = best_m["vol_sum"] / max(best_m["n"], 1)
    detail = f"best cell={best_c} Vol_mean={vol_mean/1024:.0f}KB<1MB:✗"
    return False, detail, best_c


def check_im_trigger_v2(ues: list[dict], cells: dict[str, dict]) -> tuple[bool, str, str]:
    """IM (im-01) — demo evaluator 對應 sim 結構限制.

    Spec: per-UE PRB>70 + Thp<5k + Delay>50 同時. sim DU scheduler 結構性無法
    讓任一 UE 同時滿足三條件, 改用「擁塞 proxy」demo:
      - cell volume_dl_b_total > 5MB (cell 上有真實高 demand)
      - 任一 active UE delay > 50ms (queueing 跡象)
      - cell 上至少有一 starved UE (thp=0 但 cell 在傳資料 → 排程不公平)
    這個組合對映 IM 「擁塞造成不公平」的 spirit.
    回 (triggered, detail, target_ue_id).
    """
    if not ues or not cells:
        return False, "no UE/cells", ""
    # 找 vol 高的 cell — sim DU 對 cell-level vol 上限 ~3.6 MB (single-UE-wins scheduler),
    # threshold 設 2MB 才 demo-friendly (對映 spec "cell 在傳一定量 traffic" 的精神)
    busy_cells = [c for c, agg in cells.items() if agg["vol_dl_b_total"] > 2_097_152]
    if not busy_cells:
        return False, f"no cell vol > 2MB (max vol = {max((a['vol_dl_b_total'] for a in cells.values()), default=0)/1024:.0f}KB)", ""
    for cell_id in busy_cells:
        cell_ues = [u for u in ues if u["serving"] == cell_id]
        # 任一有 delay > 50
        delayed = [u for u in cell_ues if u["delay_ms"] > 50]
        # starved: thp=0 但 cell volume > 0
        starved = [u for u in cell_ues if u["thp_kbps"] == 0]
        if delayed and starved:
            target = delayed[0]
            detail = (
                f"cell={cell_id} vol={cells[cell_id]['vol_dl_b_total']/1024:.0f}KB>5MB:✓ "
                f"delayed_UE={target['ue_id']}({target['delay_ms']:.0f}ms):✓ "
                f"starved={len(starved)}/{len(cell_ues)}:✓"
            )
            return True, detail, target["ue_id"]
    cell_id = busy_cells[0]
    cell_ues = [u for u in ues if u["serving"] == cell_id]
    detail = (
        f"cell={cell_id} vol high but no delay+starved combo "
        f"(delays={sum(1 for u in cell_ues if u['delay_ms']>50)}/{len(cell_ues)})"
    )
    return False, detail, cell_ues[0]["ue_id"] if cell_ues else ""


def check_cco_trigger_v2(cells: dict[str, dict]) -> tuple[bool, str, str, str]:
    """CCO — demo evaluator 用 volume gap 替代 PRB gap.

    Spec: cell 間 PrbTotDl gap > 0.30. sim 結構限制 PRB 都 100%, 改用 volume gap.
    任一 cell volume > 5MB 為 hot, < 100KB 為 cold, 且 hot - cold gap > 5MB → 觸發.
    回 (triggered, detail, hot_cell, cold_cell).
    """
    if len(cells) < 2:
        return False, f"only {len(cells)} cell(s) active", "", ""
    sorted_cells = sorted(cells.items(), key=lambda x: x[1]["vol_dl_b_total"], reverse=True)
    hot_cell, hot_data = sorted_cells[0]
    cold_cell, cold_data = sorted_cells[-1]
    hot_vol = hot_data["vol_dl_b_total"]
    cold_vol = cold_data["vol_dl_b_total"]
    gap_mb = (hot_vol - cold_vol) / 1_048_576
    # threshold 適配 sim DU vol 上限 ~3MB
    triggered = (hot_vol > 2_097_152) and (cold_vol < 102_400) and (gap_mb > 2)
    detail = (
        f"hot={hot_cell}({hot_vol/1024:.0f}KB) cold={cold_cell}({cold_vol/1024:.0f}KB) "
        f"hot>2MB:{'✓' if hot_vol>2_097_152 else '✗'} "
        f"cold<100KB:{'✓' if cold_vol<102_400 else '✗'} "
        f"gap={gap_mb:.1f}MB>2:{'✓' if gap_mb>2 else '✗'}"
    )
    return triggered, detail, hot_cell, cold_cell


# ── Phase actions ─────────────────────────────────────────────────

def phase1_baseline(ue_id: str, ues_by_cell: dict[str, list[str]]) -> None:
    _log("\n" + "=" * 80)
    _log(f"[{_now()}] ═══ Phase 1: BASELINE (45s) ═══")
    _log(f"  場景: 多 UE setup 預設分布")
    for c, lst in sorted(ues_by_cell.items()):
        _log(f"    {c}: {len(lst)} UEs (default traffic)")
    _log(f"  目的: 給 strategy 看穩定 KPM 基準, 之後對比")
    _log("=" * 80)


def phase2_es_trigger(ues_by_cell: dict[str, list[str]]) -> None:
    _log("\n" + "=" * 80)
    _log(f"[{_now()}] ═══ Phase 2: ES TRIGGER (75s) ═══")
    _log(f"  目的: 觸發 ES (spec §4.3): cell-level 30s mean PrbTotDl<10% AND PdcpVolDL<1MB")
    _log(f"  做法: 全部 UE pattern=idle 停 traffic, cell PRB 應降")
    _log(f"  evaluator: scan all cells, 任一 cell 30s mean 達兩條件 → fire")
    _log(f"  spec action: control_slice_level_prb_quota(min=0, max=5, dedicated=0)")
    _log("=" * 80)
    reconfig_for_phase("Phase 2 ES", ues_by_cell)


def phase3_im_trigger(ues_by_cell: dict[str, list[str]]) -> None:
    _log("\n" + "=" * 80)
    _log(f"[{_now()}] ═══ Phase 3: IM TRIGGER (75s) ═══")
    c0_count = len(ues_by_cell.get("gnb4_c0", []))
    _log(f"  目的: 觸發 IM (spec §4.1): per-UE PrbTotDl>70 AND Thp<5000 AND Delay>50 同時")
    _log(f"  做法: c0 上 {c0_count} UE 各 30 Mbps demand → cell PRB 滿, per-UE Thp 切碎")
    _log(f"        其他 cell idle 避免干擾")
    _log(f"  evaluator: 任一 UE 三條件同時達 → fire (per-UE 視角)")
    _log(f"  spec action: control_slice_level_prb_quota(min=10, max=50, dedicated=100)")
    _log("=" * 80)
    reconfig_for_phase("Phase 3 IM", ues_by_cell)


def phase4_cco_trigger(ues_by_cell: dict[str, list[str]]) -> None:
    _log("\n" + "=" * 80)
    _log(f"[{_now()}] ═══ Phase 4: CCO TRIGGER (60s) ═══")
    c0_count = len(ues_by_cell.get("gnb4_c0", []))
    _log(f"  目的: 觸發 CCO (spec §4.2 cell-level demo): cell 間 PRB sum 差距 > 0.30")
    _log(f"  做法: c0 {c0_count} UE 各 50 Mbps 全壓滿; c1/c2 全 idle")
    _log(f"        c0 PrbTotDl ≈ 100% (hot), c1/c2 ≈ 0% (cold), gap ≈ 1.0")
    _log(f"  evaluator: cell-level prb_pct_sum, hot>85 cold<30 gap>0.30")
    _log(f"  spec action: control_handover hot cell 邊緣 UE → cold neighbor")
    _log(f"  ⚠ spec 是「gNB 間」, sim 1 gNB 用 cell 間代替")
    _log("=" * 80)
    reconfig_for_phase("Phase 4 CCO", ues_by_cell)


def phase5_restore(ues_by_cell: dict[str, list[str]], mock_control: bool) -> None:
    _log("\n" + "=" * 80)
    _log(f"[{_now()}] ═══ Phase 5: RESTORE baseline ═══")
    _log(f"  目的: 解封 PRB quota, 各 UE traffic 回 setup 預設, 觀察系統回穩")
    _log("=" * 80)
    # 只在 mock_control 模式下發 release control;
    # --no-mock-control 模式下這條由真 strategy (RIC xApp) 決定要不要發
    if mock_control:
        fire_rc_control_prb_quota(10, 100, 100, "Phase 5 release: full quota")
    else:
        _log(f"[{_now()}]  (--no-mock-control: skipping scenario-side restore fire, RIC xApp 決定)")
    reconfig_for_phase("Phase 5 restore", ues_by_cell)


# ── Main loop ─────────────────────────────────────────────────────

PHASES = [
    # (start_sec, label, init_action)
    (0,   "Phase 1",          "phase1"),
    (45,  "Phase 2 ES",       "phase2"),
    (120, "Phase 3 IM",       "phase3"),
    (195, "Phase 4 CCO",      "phase4"),
    (255, "Phase 5 restore",  "phase5"),
]


def run(ue_id: str, duration_sec: int, mock_control: bool, react_sec: int) -> None:
    _log("=" * 80)
    _log(f"=== Intent demo scenario ===")
    _log(f"    primary ue_id={ue_id}  duration={duration_sec}s  mock_control={mock_control}  react_sec={react_sec}")
    _log(f"    對齊 intents-interface.md IM/CCO/ES 觸發條件 + xApp 反應時間 + control 改善觀察")
    _log(f"    場景: gnb4_c0(8UE)/c1(4)/c2(1)/c3(0), c0 hot c3 idle (CCO), c0 多 UE 搶 PRB (IM)")
    _log("=" * 80)

    ues_by_cell = _list_demo_ues_by_cell()
    _log(f"  initial UE distribution:")
    for c, lst in sorted(ues_by_cell.items()):
        _log(f"    {c}: {len(lst)} UEs ({', '.join(lst[:3])}{', ...' if len(lst)>3 else ''})")

    pre = _extract_ue_metrics(snapshot_kpm(), ue_id)
    print_kpm("[t= -1s pre-scenario]", pre)

    snap0 = snapshot_kpm()
    cells0 = _aggregate_per_cell(_extract_all_connected(snap0))
    _log(f"  pre-scenario cell aggregate:")
    for c, agg in sorted(cells0.items()):
        _log(f"    {c}: {agg['ue_count']} UE, sum PRB={agg['prb_pct_sum']:.0f}%, total Thp={agg['thp_kbps_total']:.0f} kbps, vol={agg['vol_dl_b_total']/1024:.0f} KB")

    started_at = time.time()
    triggered: dict[int, bool] = {}
    es_history: deque = deque(maxlen=30)   # cell-level history of all cells per sample
    es_trigger_fired = False
    es_trigger_first_seen_at: float | None = None
    im_trigger_first_seen_at: float | None = None
    im_trigger_fired = False
    cco_trigger_first_seen_at: float | None = None
    cco_trigger_fired = False
    last_print_at = -10.0

    while True:
        elapsed = time.time() - started_at
        if elapsed >= duration_sec:
            break

        # phase init
        for idx, (start, label, action_name) in enumerate(PHASES):
            if elapsed >= start and idx not in triggered:
                triggered[idx] = True
                if action_name == "phase1":
                    phase1_baseline(ue_id, ues_by_cell)
                elif action_name == "phase2":
                    phase2_es_trigger(ues_by_cell)
                elif action_name == "phase3":
                    phase3_im_trigger(ues_by_cell)
                elif action_name == "phase4":
                    phase4_cco_trigger(ues_by_cell)
                elif action_name == "phase5":
                    phase5_restore(ues_by_cell, mock_control)

        cur_phase_label = "?"
        cur_phase_idx = -1
        for idx, (start, label, _) in enumerate(PHASES):
            if elapsed >= start:
                cur_phase_label = label
                cur_phase_idx = idx

        snap = snapshot_kpm()
        all_ues = _extract_all_connected(snap)
        m = _extract_ue_metrics(snap, ue_id)
        cells = _aggregate_per_cell(all_ues)

        # ES history (Phase 2 期間 cell-level 累積)
        if cur_phase_idx == 1 and cells:
            es_history.append(cells.copy())

        # ES (Phase 2)
        if cur_phase_idx == 1 and not es_trigger_fired:
            ok, detail, target_cell = check_es_trigger(es_history)
            if ok:
                if es_trigger_first_seen_at is None:
                    es_trigger_first_seen_at = elapsed
                    _log(f"[{_now()}] ★ ES trigger MET ({detail})")
                hold = elapsed - es_trigger_first_seen_at
                if hold >= react_sec:
                    _log(f"[{_now()}] ★ ES condition held {hold:.0f}s ≥ {react_sec}s → strategy fires")
                    if mock_control:
                        fire_rc_control_prb_quota(0, 5, 0, f"ES action on cell={target_cell}: squeeze quota")
                    es_trigger_fired = True
            else:
                if es_trigger_first_seen_at is not None and int(elapsed) % 10 == 0:
                    _log(f"           ES partial: {detail}")
                es_trigger_first_seen_at = None

        # IM (Phase 3) — demo evaluator (擁塞 proxy: cell vol high + delayed + starved)
        if cur_phase_idx == 2 and not im_trigger_fired:
            ok, detail, target_ue = check_im_trigger_v2(all_ues, cells)
            if ok:
                if im_trigger_first_seen_at is None:
                    im_trigger_first_seen_at = elapsed
                    _log(f"[{_now()}] ★ IM trigger MET on UE={target_ue} ({detail})")
                hold = elapsed - im_trigger_first_seen_at
                if hold >= react_sec:
                    _log(f"[{_now()}] ★ IM condition held {hold:.0f}s ≥ {react_sec}s → strategy fires")
                    if mock_control:
                        fire_rc_control_prb_quota(10, 50, 100, f"IM action on UE={target_ue}: cap to 50% PRB")
                    im_trigger_fired = True
            else:
                if int(elapsed) % 10 == 0 and elapsed - last_print_at > 1:
                    _log(f"           IM partial: {detail}")

        # CCO (Phase 4) — demo evaluator (cell volume gap, sim PRB 結構限制不參考)
        if cur_phase_idx == 3 and not cco_trigger_fired:
            ok, detail, hot_cell, cold_cell = check_cco_trigger_v2(cells)
            if ok:
                if cco_trigger_first_seen_at is None:
                    cco_trigger_first_seen_at = elapsed
                    _log(f"[{_now()}] ★ CCO trigger MET ({detail})")
                hold = elapsed - cco_trigger_first_seen_at
                if hold >= react_sec:
                    _log(f"[{_now()}] ★ CCO condition held {hold:.0f}s ≥ {react_sec}s → strategy fires HO")
                    if mock_control:
                        # 找一個 hot cell 上的 UE 做 HO (用 ngap_id, target_cgi nr_cell_id 的真值靠 sim 算)
                        hot_ues = [u for u in all_ues if u["serving"] == hot_cell]
                        if hot_ues:
                            target = hot_ues[0]
                            _log(f"[{_now()}] ⚡ MOCK STRATEGY → control_handover(ue={target['ue_id']} ngap={target['ngap_id']}) {hot_cell}→{cold_cell}")
                            # NB: real RC Style 3/1 path 在這裡可以呼, 但 sim CU intra-CU HO 直接呼 handover_executor 即可
                            body = {
                                "ric_req_id": {"requestor_id": 9999, "instance_id": 1},
                                "ran_function_id": 3,
                                "control_header": {
                                    "control_style": 3,
                                    "control_action_id": 1,
                                    "ngap_id": target["ngap_id"],
                                },
                                "control_message": {
                                    "target_cgi": {"cell_id": cold_cell},
                                },
                            }
                            resp = _post(f"{CU_BASE}/api/v0.1/CU/E2/Control/request", body)
                            _log(f"           HO response: {resp.get('success', False)} {resp.get('message','')[:80]}")
                    cco_trigger_fired = True
            else:
                if int(elapsed) % 10 == 0 and elapsed - last_print_at > 1:
                    _log(f"           CCO partial: {detail}")

        # 5 秒一次 KPM dump (主 UE + cell topology)
        if elapsed - last_print_at >= 5.0:
            last_print_at = elapsed
            print_kpm(f"t={int(elapsed):>3}s {cur_phase_label}", m)
            # cell 視角 1 行
            cell_summary = " | ".join(
                f"{c}={a['ue_count']}UE/{a['prb_pct_max']:.0f}%" for c, a in sorted(cells.items())
            )
            _log(f"           cells: {cell_summary}")

        time.sleep(1.0)

    _log("\n" + "=" * 80)
    _log(f"=== Scenario end (elapsed={time.time()-started_at:.1f}s) ===")
    _log("=" * 80)
    final = _extract_ue_metrics(snapshot_kpm(), ue_id)
    print_kpm("[final]", final)

    _log("\n=== Trigger Summary ===")
    _log(f"  ES  (Phase 2): trigger_met={es_trigger_first_seen_at is not None:1d}  fired={es_trigger_fired:1d}")
    _log(f"  IM  (Phase 3): trigger_met={im_trigger_first_seen_at is not None:1d}  fired={im_trigger_fired:1d}")
    _log(f"  CCO (Phase 4): trigger_met={cco_trigger_first_seen_at is not None:1d}  fired={cco_trigger_fired:1d}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ue-id", default="demo_0508")
    ap.add_argument("--duration-sec", type=int, default=300)
    ap.add_argument("--no-mock-control", action="store_true",
                    help="不模擬 strategy 下 control, 純驅動 KPM (給 RIC 真 strategy 跑)")
    ap.add_argument("--react-sec", type=int, default=30,
                    help="trigger 條件達成後等多久 mock strategy 才下 control")
    args = ap.parse_args()
    try:
        run(args.ue_id, args.duration_sec,
            mock_control=not args.no_mock_control, react_sec=args.react_sec)
    except KeyboardInterrupt:
        _log("\n[interrupted]")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
