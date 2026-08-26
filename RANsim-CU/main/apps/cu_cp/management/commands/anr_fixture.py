"""劇本內建的病徵時間軸執行器(2026-08-26)。

第 6、7 題這類「病發 → xApp 止血 → 管理面修好 → xApp 確認恢復」的題目,
中段的「修好」屬管理面職權,xApp 不能自己做 —— 過去是由人手動跑 q6_restore,
等於測試依賴外部觸發。這支把整段節奏宣告在劇本的 `anr_fixture` 區塊裡,
由 CU 自己照條件推進,不需要人介入。

**為什麼仍然是在考事件而不是考時間**:劇本的排程改變的是「環境什麼時候被修好」
(等同真實維運人員某時刻動手);xApp 不知道這張時刻表,它依然只能靠觀測
`xnX2Established` 變化才會反應。且修復步驟預設是**條件觸發**(等 xApp 真的
止血了才起算),避免劇本比 xApp 早動作、病自己好掉導致三段節奏跑不完。

用法(背景執行,不佔前景):
    docker exec -d ransim-cu python manage.py anr_fixture anr_xn_discovery

劇本區塊格式:
    "anr_fixture": {"steps": [
      {"do":"relation","src":"s07_c0","tgt":"n33_c0","set":{"xn_x2_established":false}},
      {"do":"move_ues","prefix":"xd","to":"s07_c0"},
      {"wait_until":{"src":"s07_c0","tgt":"n33_c0","field":"xn_blocklist","equals":true},
       "timeout_sec":3600,"note":"等 xApp 止血"},
      {"sleep_sec":300,"note":"維運排程時間"},
      {"do":"relation","src":"s07_c0","tgt":"n33_c0","set":{"xn_x2_established":true}}
    ]}
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand

SCENARIO_DIRS = [Path("/app/docs/scenarios"), Path("docs/scenarios")]
POLL_SEC = 5.0


def _load_steps(scenario_id: str) -> list[dict[str, Any]]:
    for d in SCENARIO_DIRS:
        p = d / f"{scenario_id}.json"
        if p.exists():
            spec = json.loads(p.read_text(encoding="utf-8"))
            return (spec.get("anr_fixture") or {}).get("steps") or []
    raise FileNotFoundError(f"找不到劇本 {scenario_id}.json(試過 {SCENARIO_DIRS})")


class Command(BaseCommand):
    help = "依劇本的 anr_fixture 時間軸自動推進病徵(免人工觸發)"

    def add_arguments(self, parser):
        parser.add_argument("scenario_id")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation as R
        from main.apps.cu_cp.models.ue_context import UeContext
        from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
        from main.apps.cu_cp.services.common.timestamp_service import TimestampService

        sid = opts["scenario_id"]
        steps = _load_steps(sid)
        if not steps:
            self.stdout.write(f"[fixture] {sid} 沒有 anr_fixture 區塊,結束")
            return
        if opts.get("dry_run"):
            self.stdout.write(f"[fixture] {sid} 乾跑,不執行任何動作:")
            for i, st in enumerate(steps, 1):
                kind = ("wait_until" if "wait_until" in st else
                        "sleep" if "sleep_sec" in st else st.get("do", "?"))
                self.stdout.write(f"   {i}. {kind:11s} {st.get('note', '')}")
            return
        self.stdout.write(f"[fixture] {sid}:{len(steps)} 個步驟開始")

        for i, st in enumerate(steps, 1):
            note = st.get("note", "")
            if "wait_until" in st:
                w = st["wait_until"]
                deadline = time.time() + float(st.get("timeout_sec", 3600))
                self.stdout.write(f"[fixture] {i}. 等待 {w['src']}→{w['tgt']}.{w['field']}=={w['equals']} {note}")
                hit = False
                while time.time() < deadline:
                    rel = R.objects.filter(source_cell_id=w["src"], target_cgi=w["tgt"]).first()
                    if rel is not None and bool(getattr(rel, w["field"])) == bool(w["equals"]):
                        hit = True
                        break
                    time.sleep(POLL_SEC)
                self.stdout.write(f"[fixture] {i}. {'條件成立' if hit else '逾時(仍往下走)'}")
                continue

            if "sleep_sec" in st:
                self.stdout.write(f"[fixture] {i}. 等 {st['sleep_sec']}s {note}")
                time.sleep(float(st["sleep_sec"]))
                continue

            act = st.get("do")
            if act == "relation":
                fields = dict(st.get("set") or {})
                fields["updated_at"] = TimestampService.now()
                n = R.objects.filter(source_cell_id=st["src"], target_cgi=st["tgt"]).update(**fields)
                self.stdout.write(f"[fixture] {i}. set {st['src']}→{st['tgt']} {st.get('set')} rows={n} {note}")
            elif act == "move_ues":
                moved = sum(
                    1 for u in UeContext.objects.filter(ue_id__startswith=st["prefix"]).exclude(serving_cell=st["to"])
                    if execute_f1_handover(ue_id=u.ue_id, target_cell=st["to"], trigger="MANUAL")
                )
                self.stdout.write(f"[fixture] {i}. 搬 {moved} 台 UE → {st['to']} {note}")
            elif act == "barred":
                from main.apps.cu_cp.models.cell_config import CellConfig
                n = CellConfig.objects.filter(cell_id=st["cell"]).update(is_barred=bool(st.get("value", True)))
                self.stdout.write(f"[fixture] {i}. {st['cell']} barred={st.get('value', True)} rows={n} {note}")
            else:
                self.stdout.write(f"[fixture] {i}. 未知步驟 {act},跳過")
        self.stdout.write(f"[fixture] {sid} 時間軸執行完畢")
