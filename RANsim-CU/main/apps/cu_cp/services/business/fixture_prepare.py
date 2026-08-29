"""起場前準備 —— round_reset.sh 三機制的正式歸宿(2026-08-28 收官後搬家)。

十二題戰役裡,這三件事決定了一輪是「乾淨出生」還是「帶病出生」,
但它們一直住在 shell 腳本裡,前端 Start Sim 走不到:

  1. 掃+等靜默驗證:上一輪的量測還在對方 60s 聚合窗裡時就起場,
     對方會拿餘料回寫 ADD(Q4 五輪:清完 8 條又長回來)。要求連續
     90s 無新關係且量測排空,對手的記憶確定吐完才算乾淨。
  2. pre 區(結構與場同生):CellConfig → 關係 → 容量覆寫,全部在
     場出生前寫入 —— 量測流起點晚於一切結構,任何 watch 無從在
     ④ 前開錶(Q9 出生鏈公理)。
  3. barred 預埋:禁閉屬性與場同生(Q4:T0→④ 空窗一筆合法重建
     就把考點資格永久取消)。

錯誤處理原則:fail-loud(Q11 教訓 —— 三層吞錯讓 NOT NULL 連環失敗
靜默了兩輪)。這裡任何一段失敗都寫進回傳的 errors,呼叫端自己決定
擋不擋,但絕不無聲。
"""
from __future__ import annotations

import json
import logging
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCENARIO_DIRS = [Path("/app/docs/scenarios"), Path("docs/scenarios")]
SWEEP_INTERVAL_SEC = 5.0
SWEEP_STREAK_NEED = 18          # 18 × 5s = 90s > 對方 60s 聚合窗
SWEEP_MAX_SEC = 300.0


def _load_scenario(scenario_id: str) -> dict[str, Any]:
    for d in SCENARIO_DIRS:
        p = d / f"{scenario_id}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"scenario {scenario_id}.json not found in {SCENARIO_DIRS}")


def _kill_stale_timelines() -> int:
    """殺掉殘存時間軸 + 清鎖/進度/心跳(Q9 三輪:殭屍經續跑機制復活擋新輪)。"""
    import glob
    import os
    import signal
    killed = 0
    me = os.getpid()
    for p in glob.glob("/proc/[0-9]*/cmdline"):
        try:
            pid = int(p.split("/")[2])
            if pid == me:
                continue
            if "anr_fixture" in open(p, "rb").read().decode(errors="ignore"):
                os.kill(pid, signal.SIGKILL)
                killed += 1
        except (OSError, ValueError):
            continue
    for f in ("anr_fixture.lock", "anr_fixture.progress.json",
              "anr_fixture.current", "anr_fixture.heartbeat",
              "fixture_barred.json", "ho_force_fail.txt"):
        try:
            Path(f"/app/tmp/{f}").unlink()
        except OSError:
            pass
    return killed


def _wipe_state() -> None:
    """清上一場 RAN 狀態(世界應已靜止 —— 呼叫端保證 sim 已停)。"""
    from main.apps.cu_cp.models.cell_config import CellConfig
    from main.apps.cu_cp.models.handover_event import HandoverEvent
    from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
    from main.apps.cu_cp.models.nr_relation_change_event import NrRelationChangeEvent
    from main.apps.cu_cp.models.rlf_event import RlfEvent
    from main.apps.cu_cp.models.ue_context import UeContext
    for m in (NrCellRelation, HandoverEvent, RlfEvent,
              NrRelationChangeEvent, UeContext):
        m.objects.all().delete()
    CellConfig.objects.update(is_barred=False)


def _meas_rate() -> float:
    from main.apps.cu_cp.services.business.anr_kpm import meas_aggregate
    try:
        aggs = meas_aggregate(window_min=1.0) or []
        return sum(float(a.get("sampleRatePerMin") or 0) for a in aggs)
    except Exception:  # noqa: BLE001 — 量測面壞掉時當 0,靠 streak 撐住
        return 0.0


def _sweep_and_wait() -> dict[str, Any]:
    """每輪掃掉關係,要求連續 90s 無新關係且量測排空。"""
    from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation as NR
    streak, tries = 0, 0
    deadline = time.time() + SWEEP_MAX_SEC
    last = ""
    while time.time() < deadline:
        tries += 1
        n = NR.objects.count()
        NR.objects.all().delete()
        meas = _meas_rate()
        clean = (n == 0 and meas < 1)
        streak = streak + 1 if clean else 0
        last = "CLEAN" if clean else f"DIRTY rels={n} meas={meas:.0f}"
        if streak >= SWEEP_STREAK_NEED:
            return {"quiet": True, "tries": tries, "last": last}
        time.sleep(SWEEP_INTERVAL_SEC)
    return {"quiet": False, "tries": tries, "last": last}


def _apply_pre(spec: dict[str, Any], errors: list[str]) -> dict[str, int]:
    """pre 區:env 覆寫(每輪 replace)+ CellConfig(含 inactive 幽靈)+ 關係。"""
    from main.apps.cu_cp.models.cell_config import CellConfig as CC
    from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation as NR
    from main.apps.cu_cp.services.common.timestamp_service import TimestampService
    from main.apps.cu_cp.services.common.uuid_service import UUIDService
    from main.utils.env_loader import set_overrides

    pre = (spec.get("anr_fixture") or {}).get("pre") or {}
    set_overrides(dict(pre.get("env") or {}), replace=True)

    now = TimestampService.now()
    # cells:劇本 gnbs 全員自動導出 + pre.cells 額外項(如 inactive 幽靈)
    # gnb 必填:pre-birth 若留 NULL,seeder 的「同 gNB 互種」會把 NULL==NULL
    # 當同站 → 全場互種滿 mesh(Q9 複測實錄:全場→n77 被種滿、attempt_add
    # 撞已存在變 upsert、零 ADD_REJECTED、考題死)。昨天靠 DU 註冊先補
    # gnb_id 的競態躲過 —— 出生鏈公理第十例:欄位也要與場同生。
    derived = [{"cell_id": c["cell_id"], "pci": c["pci"], "gnb": g.get("name") or c["cell_id"],
                "frequency_ghz": g.get("frequency_ghz", 3.5),
                "bandwidth_mhz": g.get("bandwidth_mhz", 40.0)}
               for g in spec.get("gnbs", []) for c in g.get("cells", [])]
    have = {x["cell_id"] for x in derived}
    cells = derived + [c for c in (pre.get("cells") or [])
                       if c["cell_id"] not in have]
    n_cells = 0
    for c in cells:
        try:
            row = CC.objects.filter(cell_id=c["cell_id"]).first()
            if row is None:
                du = (CC.objects.exclude(served_by_du_id=None)
                      .values_list("served_by_du_id", flat=True).first())
                CC.objects.create(
                    cell_id=c["cell_id"], cell_uuid=UUIDService.random_uuid(),
                    pci=int(c["pci"]),
                    frequency_ghz=float(c.get("frequency_ghz") or 3.5),
                    bandwidth_mhz=float(c.get("bandwidth_mhz") or 40.0),
                    served_by_du_id=du, is_active=bool(c.get("active", True)),
                    gnb_id=c.get("gnb") or c["cell_id"],
                    created_at=now, updated_at=now)
            else:
                CC.objects.filter(pk=row.pk).update(
                    pci=int(c["pci"]), is_active=bool(c.get("active", True)),
                    gnb_id=c.get("gnb") or c["cell_id"])
            n_cells += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"pre cell {c.get('cell_id')}: {e}")

    n_rels = 0
    for r in (pre.get("relations") or []):
        try:
            age = float(r.get("age_sec") or 0)
            f = dict(r.get("set") or {})
            NR.objects.get_or_create(
                source_cell_id=r["src"], target_cgi=r["tgt"],
                defaults=dict(target_pci=int(r.get("pci") or 0),
                              target_arfcn=int(r.get("arfcn") or 633333),
                              target_rat="NR", xn_x2_established=True,
                              created_at=now - timedelta(seconds=age),
                              updated_at=now, **f))
            n_rels += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"pre relation {r.get('src')}→{r.get('tgt')}: {e}")
    return {"cells": n_cells, "relations": n_rels}


def _seed_barred(spec: dict[str, Any]) -> list[str]:
    """enforce.barred → fixture_barred 檔(禁閉屬性與場同生)。"""
    from main.apps.cu_cp.services.common.fixture_state import set_fixture_barred
    barred = ((spec.get("anr_fixture") or {}).get("enforce") or {}).get("barred") or []
    if barred:
        set_fixture_barred(sorted(barred))
    return barred


def prepare(scenario_id: str) -> dict[str, Any]:
    """起場前完整準備。呼叫時機:sim 已停、scene 尚未 apply。"""
    errors: list[str] = []
    spec = _load_scenario(scenario_id)
    # 抑制閥先豎(復活鉤 vs 清理者:清理期間任何行程不得續跑舊時間軸)
    Path("/app/tmp/anr_fixture.suppress").write_text("prepare")
    killed = _kill_stale_timelines()
    time.sleep(1.0)
    killed += _kill_stale_timelines()   # 二次收割:清理瞬間可能有復活中的行程
    _wipe_state()
    sweep = _sweep_and_wait()
    if not sweep["quiet"]:
        errors.append(f"sweep not quiet after {SWEEP_MAX_SEC}s: {sweep['last']}")
    pre = _apply_pre(spec, errors)
    barred = _seed_barred(spec)
    try:
        Path("/app/tmp/anr_fixture.suppress").unlink()
    except OSError:
        pass
    out = {"scenario": scenario_id, "killed_timelines": killed,
           "sweep": sweep, "pre": pre, "barred": barred, "errors": errors}
    logger.info("fixture prepare %s: %s", scenario_id, out)
    return out
