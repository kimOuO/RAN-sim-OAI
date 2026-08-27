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
from datetime import timedelta
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
        parser.add_argument("scenario_id", nargs="?", default="")
        parser.add_argument("--status", action="store_true",
                            help="只讀心跳,回報時間軸是否還活著(不啟動任何步驟)")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--from-step", type=int, default=1,
                            help="從第 N 步開始(補跑用,1-based)")
        parser.add_argument("--resume-elapsed", type=float, default=0.0,
                            help="續跑時,起始步驟已經過的秒數(只影響第一個步驟的等待)")


    def _maintain(self, spec, last_ts):
        """等待期間持續維持病徵的觀測條件(RIC 第四十八輪要求)。

        閉環的固有問題:xApp 的處置會改變 UE 分布 —— 止血後沒得換手,UE 可能
        飄到別的 cell,病徵就自己停了(今天第 7 題前兩次死鎖的原因)。等待步驟
        每 30 秒把 UE 拉回來源 cell,確保「有人持續想換手」這個前提不消失。
        """
        import time as _t
        if not spec or (_t.time() - last_ts) < 30:
            return last_ts
        from main.apps.cu_cp.models.ue_context import UeContext
        from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
        moved = sum(1 for u in UeContext.objects.filter(ue_id__startswith=spec["prefix"])
                    .exclude(serving_cell=spec["to"])
                    if execute_f1_handover(ue_id=u.ue_id, target_cell=spec["to"], trigger="MANUAL"))
        if moved:
            self.stdout.write(f"[fixture]    ↻ 維持條件:把 {moved} 台 UE 拉回 {spec['to']}")
        return _t.time()

    PROGRESS = "/app/tmp/anr_fixture.progress.json"

    def _save_progress(self, sid, step_no, started=None):
        """把「跑到第幾步、這一步何時開始」寫檔,讓 CU 重啟後接得回來。

        2026-08-26 第 6 題:時間軸跑在 CU 容器裡,CU 15:33 重啟就整個死在等待步驟,
        沒有任何東西接手,最後由人手動補完最後一步 —— 那一輪因此不能算無人值守。
        心跳只讓「死了」看得出來,要真的活下去必須有落盤與續跑。
        """
        import json as _j, time as _t
        from pathlib import Path as _P
        try:
            _P(self.PROGRESS).write_text(_j.dumps(
                {"scenario": sid, "step": step_no,
                 # 續跑時要沿用原本的起算時間,不能重新戳一次 —— 否則每重啟一次
                 # 這一步就從頭算起,連續重啟會讓 300 秒的等待永遠跑不完。
                 # (2026-08-27 實測:第二次重啟後顯示「該步已過 6s」而非 95s)
                 "step_started": started if started is not None else _t.time()}))
        except OSError:
            pass

    def _clear_progress(self):
        from pathlib import Path as _P
        try:
            _P(self.PROGRESS).unlink()
        except OSError:
            pass

    def _beat(self, sid, step_no, kind, note=""):
        """心跳:證明時間軸「活著」,而不是「日誌裡有行」。

        2026-08-26 事故:CU 在 15:33 重啟,時間軸連同 CU 行程一起被殺,死在
        等待步驟裡。我看日誌尾巴還有 `維持條件` 舊行,就據此回報「劇本在跑、
        300 秒後會自動翻 xn」—— 對內對外都報了假消息,對方白等 40 分鐘。
        日誌是「過去發生過」的證據,不是「現在還活著」的證據;要判活性就得有
        一個會隨時間前進的欄位。
        """
        import json as _j, os as _o, time as _t
        from pathlib import Path as _P
        try:
            _P("/app/tmp/anr_fixture.heartbeat").write_text(_j.dumps({
                "scenario": sid, "pid": _o.getpid(), "ts": _t.time(),
                "step": step_no, "kind": kind, "note": note,
            }, ensure_ascii=False))
        except OSError:
            pass  # 心跳寫不進去不該讓時間軸掛掉

    def _report_status(self):
        """回報時間軸活性 —— 判準是心跳新鮮度 + 行程存在,兩者都要。

        心跳新但行程不在(容器剛重啟)= 死;行程在但心跳舊 = 卡住。
        兩種都不是「在跑」,而看日誌完全分不出來。
        """
        import json as _j, time as _t
        from pathlib import Path as _P
        hb = _P("/app/tmp/anr_fixture.heartbeat")
        if not hb.exists():
            self.stdout.write("[fixture] 無心跳檔 —— 沒有時間軸跑過(或已清空)")
            return
        try:
            d = _j.loads(hb.read_text())
        except (ValueError, OSError) as e:
            self.stdout.write(f"[fixture] 心跳檔讀不出來:{e}")
            return
        age = _t.time() - float(d.get("ts") or 0)
        proc = _P(f"/proc/{d.get('pid')}").exists()
        alive = proc and age < 30  # POLL_SEC=5,30 秒沒動就是卡住或死了
        self.stdout.write(
            f"[fixture] {d.get('scenario')} 第 {d.get('step')} 步({d.get('kind')})"
            f" {d.get('note') or ''}\n"
            f"          心跳 {age:.0f} 秒前 · PID {d.get('pid')} {'在' if proc else '不在'}"
            f" → {'✅ 活著' if alive else '❌ 死了/卡住 —— 不要據此推論劇本會自己往下走'}")

    def handle(self, *args, **opts):
        from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation as R
        from main.apps.cu_cp.models.ue_context import UeContext
        from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
        from main.apps.cu_cp.services.common.timestamp_service import TimestampService

        sid = opts["scenario_id"]
        if opts.get("status"):
            self._report_status()
            return
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

        _first = int(opts.get("from_step") or 1)
        for i, st in enumerate(steps, 1):
            if i < _first:
                continue
            note = st.get("note", "")
            _kind = ("wait_until" if "wait_until" in st else
                     "wait_event" if "wait_event" in st else
                     "sleep" if "sleep_sec" in st else st.get("do", "?"))
            self._beat(sid, i, _kind, note)
            # 續跑時第一個步驟要扣掉已經過的時間,否則 CU 重啟會讓等待從頭算起
            _elapsed = float(opts.get("resume_elapsed") or 0.0) if i == _first else 0.0
            self._save_progress(sid, i,
                                started=(time.time() - _elapsed) if _elapsed else None)
            if "wait_until" in st:
                w = st["wait_until"]
                # 單欄位 {field, equals} 或多欄位 {fields:{欄位:值}} —— 成對旗標要一起等
                want = dict(w["fields"]) if "fields" in w else {w["field"]: w["equals"]}
                deadline = time.time() + float(st.get("timeout_sec", 3600))
                self.stdout.write(f"[fixture] {i}. 等待 {w['src']}→{w['tgt']} {want} {note}")
                hit = False
                _mt = 0.0
                while time.time() < deadline:
                    _mt = self._maintain(st.get("maintain"), _mt)
                    self._beat(sid, i, "wait_until", note)
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
                _mt = 0.0
                while time.time() < deadline:
                    _mt = self._maintain(st.get("maintain"), _mt)
                    self._beat(sid, i, "wait_event", note)
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
                _remain = max(0.0, float(st["sleep_sec"]) - _elapsed)
                self.stdout.write(
                    f"[fixture] {i}. 等 {st['sleep_sec']}s {note}"
                    + (f"(續跑,已過 {_elapsed:.0f}s,剩 {_remain:.0f}s)" if _elapsed else ""))
                _end = time.time() + _remain
                while time.time() < _end:  # 分段睡,長 sleep 期間仍要有心跳
                    self._beat(sid, i, "sleep", note)
                    time.sleep(min(POLL_SEC, max(0.1, _end - time.time())))
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
                    # created_age_sec:把建立時間往前挪。新生的關係天生 cum=0、
                    # 零換手,會同時踩到 xApp 的兩件事:新生兒寬限期(它會忽略這條
                    # 關係),以及第 12 題稽核(cum=0 的封鎖 = 無據封鎖)。
                    # 佈第 6 題時關係是現建的,若不回填,xApp 對它的封鎖會被自家
                    # 稽核判成無據 —— 那是我方佈場造成的假象,不是它判錯。
                    age = float(st.get("created_age_sec") or 0)
                    created = now - timedelta(seconds=age) if age else now
                    R.objects.create(
                        source_cell_id=st["src"], target_cgi=st["tgt"],
                        target_pci=(c.pci if c else 0), target_rat="NR",
                        target_arfcn=(nr_arfcn_from_ghz(c.frequency_ghz) if c else 633333),
                        xn_x2_established=True, created_at=created, updated_at=now)
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
        self._clear_progress()   # 正常跑完就不該再被續跑接手
