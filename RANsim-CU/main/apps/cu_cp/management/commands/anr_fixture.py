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
        parser.add_argument("--from-step", type=int, default=1,
                            help="從第 N 步開始(補跑用,1-based)")

    def handle(self, *args, **opts):
        from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation as R
        from main.apps.cu_cp.models.ue_context import UeContext
        from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
        from main.apps.cu_cp.services.common.timestamp_service import TimestampService

        sid = opts["scenario_id"]
        # 互斥鎖:同時跑多個時間軸會互相干擾(2026-08-26 實測:舊的孤兒行程
        # 先清掉了注入,新的還停在等待步驟,兩邊時序全亂)。
        import os
        from pathlib import Path as _P
        lock = _P("/app/tmp/anr_fixture.lock")
        if not opts.get("dry_run"):
            if lock.exists():
                try:
                    old_pid = int(lock.read_text().strip() or 0)
                except ValueError:
                    old_pid = 0
                alive = old_pid > 0 and _P(f"/proc/{old_pid}").exists()
                if alive:
                    self.stdout.write(f"[fixture] 已有另一個時間軸在跑(PID {old_pid}),拒絕啟動")
                    return
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.write_text(str(os.getpid()))
        steps = _load_steps(sid)
        if not steps:
            self.stdout.write(f"[fixture] {sid} 沒有 anr_fixture 區塊,結束")
            return
        if opts.get("dry_run"):
            self.stdout.write(f"[fixture] {sid} 乾跑,不執行任何動作:")
            for i, st in enumerate(steps, 1):
                kind = ("wait_until" if "wait_until" in st else
                        "wait_event" if "wait_event" in st else
                        "sleep" if "sleep_sec" in st else st.get("do", "?"))
                self.stdout.write(f"   {i}. {kind:11s} {st.get('note', '')}")
            return
        self.stdout.write(f"[fixture] {sid}:{len(steps)} 個步驟開始")

        for i, st in enumerate(steps, 1):
            if i < int(opts.get("from_step") or 1):
                continue
            note = st.get("note", "")
            if "wait_until" in st:
                w = st["wait_until"]
                # 單欄位 {field, equals} 或多欄位 {fields:{欄位:值}} —— 成對旗標要一起等
                want = dict(w["fields"]) if "fields" in w else {w["field"]: w["equals"]}
                deadline = time.time() + float(st.get("timeout_sec", 3600))
                self.stdout.write(f"[fixture] {i}. 等待 {w['src']}→{w['tgt']} {want} {note}")
                hit = False
                while time.time() < deadline:
                    rel = R.objects.filter(source_cell_id=w["src"], target_cgi=w["tgt"]).first()
                    if rel is not None and all(
                            bool(getattr(rel, k)) == bool(v) for k, v in want.items()):
                        hit = True
                        break
                    time.sleep(POLL_SEC)
                self.stdout.write(f"[fixture] {i}. {'條件成立' if hit else '逾時(仍往下走)'}")
                continue

            if "wait_event" in st:
                # 等某個關係上的某類事件累積到 N 次 —— 第 7 題用它等「重封」
                # (第 2 次 FLAG_SET = xApp 探測失敗後又封回去,倍增鏈才驗得到)
                from main.apps.cu_cp.models.nr_relation_change_event import (
                    NrRelationChangeEvent as CE,
                )
                w = st["wait_event"]
                need = int(w.get("min_count", 1))
                # 只算「這個步驟開始之後」的事件 —— changeEvents 表跨劇本累積,
                # 數歷來次數會把前幾輪的 FLAG_SET 也算進去,條件一啟動就成立
                # (2026-08-26 第 7 題實測:一開跑就提早清掉注入)。
                t0 = TimestampService.now()
                deadline = time.time() + float(st.get("timeout_sec", 10800))
                self.stdout.write(
                    f"[fixture] {i}. 等待 {w['src']}→{w['tgt']} 的 {w['action']} 累積 {need} 次 {note}")
                hit = False
                # preceded_by:要求該事件出現在另一種事件「之後」——
                # 第 7 題用它精準辨認「重封」:探測必然先 FLAG_CLEAR,之後的
                # FLAG_SET 才是重封。只數次數的話,xApp 的冪等重掛(同樣送成對
                # FLAG_SET)會被誤認成重封,又提早清掉注入。
                prev = w.get("preceded_by")
                while time.time() < deadline:
                    qs = CE.objects.filter(source_cell_id=w["src"], target_cgi=w["tgt"],
                                           at__gte=t0)
                    if prev:
                        last_prev = qs.filter(action=prev).order_by("-id").first()
                        n = (qs.filter(action=w["action"], id__gt=last_prev.id).count()
                             if last_prev else 0)
                    else:
                        n = qs.filter(action=w["action"]).count()
                    if n >= need:
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
                # create=true:關係不存在就先建(ANR 劇本的基準 NRT 是空的,
                # 只 update 會靜默做白工 —— 第 7 題要「既有健康關係」當前提)
                if st.get("create") and not R.objects.filter(
                        source_cell_id=st["src"], target_cgi=st["tgt"]).exists():
                    from main.apps.cu_cp.models.cell_config import CellConfig as _CC
                    from main.apps.cu_cp.services.business.anr_seeder import nr_arfcn_from_ghz
                    c = _CC.objects.filter(cell_id=st["tgt"]).first()
                    now = TimestampService.now()
                    R.objects.create(
                        source_cell_id=st["src"], target_cgi=st["tgt"],
                        target_pci=(c.pci if c else 0), target_rat="NR",
                        target_arfcn=(nr_arfcn_from_ghz(c.frequency_ghz) if c else 633333),
                        xn_x2_established=True, created_at=now, updated_at=now)
                    self.stdout.write(f"[fixture] {i}. (關係不存在 → 先建 {st['src']}→{st['tgt']})")
                n = R.objects.filter(source_cell_id=st["src"], target_cgi=st["tgt"]).update(**fields)
                self.stdout.write(f"[fixture] {i}. set {st['src']}→{st['tgt']} {st.get('set')} rows={n} {note}")
            elif act == "move_ues":
                moved = sum(
                    1 for u in UeContext.objects.filter(ue_id__startswith=st["prefix"]).exclude(serving_cell=st["to"])
                    if execute_f1_handover(ue_id=u.ue_id, target_cell=st["to"], trigger="MANUAL")
                )
                self.stdout.write(f"[fixture] {i}. 搬 {moved} 台 UE → {st['to']} {note}")
            elif act == "inject":
                # 換手失敗注入的熱開關(第 7 題):寫檔即生效、清檔即停止,不重啟容器
                from pathlib import Path as _P
                f = _P("/app/tmp/ho_force_fail.txt")
                f.parent.mkdir(parents=True, exist_ok=True)
                if st.get("clear"):
                    f.write_text("")
                    self.stdout.write(f"[fixture] {i}. 清掉失敗注入(鄰居被修好了){' ' + note if note else ''}")
                else:
                    f.write_text(f"{st['cell']},{st.get('cause', 'RandomAccessProblem')}\n")
                    self.stdout.write(
                        f"[fixture] {i}. 注入 {st['cell']} → {st.get('cause','RandomAccessProblem')} {note}")
            elif act == "barred":
                from main.apps.cu_cp.models.cell_config import CellConfig
                n = CellConfig.objects.filter(cell_id=st["cell"]).update(is_barred=bool(st.get("value", True)))
                self.stdout.write(f"[fixture] {i}. {st['cell']} barred={st.get('value', True)} rows={n} {note}")
            else:
                self.stdout.write(f"[fixture] {i}. 未知步驟 {act},跳過")
        self.stdout.write(f"[fixture] {sid} 時間軸執行完畢")
        try:
            lock.unlink()
        except (FileNotFoundError, NameError):
            pass
