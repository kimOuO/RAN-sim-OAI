"""run 級遙測封存:run 期間背景輪詢 CU(四張落地表)與 E2Adapter(ControlAudit),打上 scene_run_uuid 寫進本 DB。

為什麼不用 E2Adapter 的 KPM 快照:那是 indication 驅動(RIC 有訂閱才有),RIC 不通就永遠是空;
CU 的 MeasurementLog / CellMeasurementLog / HandoverEvent / RlfEvent 每個 PM 視窗由 F1 上報落地,與 RIC 無關。
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request
from collections import defaultdict
from typing import Any

from django.conf import settings
from django.db import close_old_connections

from main.apps.run_telemetry_archive.models.run_control_event import RunControlEvent
from main.apps.run_telemetry_archive.models.run_pm_snapshot import RunPmSnapshot
from main.apps.run_telemetry_archive.models.run_handover_event import RunHandoverEvent
from main.apps.run_telemetry_archive.models.run_kpm_sample import RunKpmSample
from main.apps.run_telemetry_archive.services.business.sqldb_operations import SqlDbBusinessService as DB
from main.apps.run_telemetry_archive.services.common.timestamp_service import TimestampService
from main.apps.run_telemetry_archive.services.common.uuid_service import UUIDService
from main.utils.logger import get_logger

logger = get_logger(__name__)
_threads: dict[str, "RunArchiver"] = {}
_lock = threading.Lock()


def _post(url: str, body: dict, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _control_items(data: Any) -> list[dict]:
    """E2Adapter ControlAuditReader 回 {"commands": [...], "count": n}(舊版曾是 list)。"""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.get("commands") or [])
    return []


def _stamp(prefix: str) -> dict[str, Any]:
    now = TimestampService.now()
    return {f"{prefix}_uuid": UUIDService.generate_uuid(prefix), f"{prefix}_created_at": now, f"{prefix}_updated_at": now}


class RunArchiver(threading.Thread):
    """一場一條執行緒。多 gNB(2026-09-27):同時輪詢每個 gNB 的 CU(落地表、full KPM 快照)與
    e2adapter(控制稽核),各自一個游標;鎖步時鐘下各 CU 的 PM 視窗序號相同,所以同一視窗的
    報告自然併成同一列。每筆 UE / cell / 事件都標上來源 gNB(node_id)與 E2 node(meid)。"""

    def __init__(self, scene_run_uuid: str, sim_dt_ms: int, poll_sec: float = 2.0, cu_host: str | None = None, e2_port: int | None = None,
                 run_seq: int = 0, ric_run: int = 0, nodes: list[dict] | None = None,
                 ue_host: str | None = None, du_host: str | None = None) -> None:
        super().__init__(name=f"archiver-{scene_run_uuid[-8:]}", daemon=True)
        self.run_uuid = scene_run_uuid
        self.run_seq = int(run_seq)
        # RIC 閘道的場次號(宣告回應的 `run`);宣告失敗或還沒回來時是 0
        self.ric_run = int(ric_run)
        self.sim_dt_ms = max(1, int(sim_dt_ms))
        self.poll_sec = poll_sec
        self._stop_evt = threading.Event()   # 不可叫 _stop:會蓋掉 Thread._stop() 讓 join() 炸
        # 最後一次從 DU 報告看到的劇本時鐘。控制事件沒有自己的時間戳,用這個近似
        # (誤差 ≤ 一個輪詢週期,比 tick 累加可靠)。None = 還沒收到過任何報告。
        self._last_scene_ms: int | None = None
        self._last_snap_ms: int | None = None   # 上次抓 full KPM 快照的劇本時間
        # 同一 run 若被再次 start,接在既有視窗後面,不從 0 重算(否則 window_index / sim_time 重複)
        last = RunKpmSample.objects.filter(f_scene_run_uuid=scene_run_uuid).order_by("-window_index").first()
        self.window_index = (last.window_index + 1) if last else 0
        self.ticks_so_far = (last.sim_time_ms // self.sim_dt_ms) if last else 0   # CellMeasurementLog.tick_count 是「窗內 tick 數」,累計才是 sim-time
        self._last_beam: dict = {}   # ue → (cell, beam_id),算波束切換次數
        self.stats = {"samples": 0, "handover": 0, "rlf": 0, "control": 0, "polls": 0, "errors": 0}
        # 舊呼叫方式(單一 CU / adapter)→ 一個沒有名字的 node
        if not nodes:
            nodes = [{"node_id": "", "meid": "", "cu_host": cu_host, "e2_port": e2_port}]
            if cu_host and cu_host.startswith("cu-") and ue_host is None:
                # 舊命名 cu-<rid> → ue-<rid> / du-<rid>(多 gNB 之前的單一實例)
                ue_host = cu_host.replace("cu-", "ue-", 1); du_host = cu_host.replace("cu-", "du-", 1)
        self.nodes: list[dict] = []
        for n in nodes:
            h = n.get("cu_host")
            cu_base = f"http://{h or settings.HTTP_CU_HOST}:{8000 if h else settings.HTTP_CU_PORT}"
            e2 = f"http://{settings.HTTP_E2ADAPTER_HOST}:{n.get('e2_port') or settings.HTTP_E2ADAPTER_PORT}/api/v0.1/E2Adapter/ControlAudit/ControlAuditReader/read"
            if settings.PER_RUN_ENABLED and not n.get("e2_port"):
                e2 = ""   # no_ric 場次沒有 e2adapter;不可退回共用 adapter(會把別人的控制稽核歸進這一場)
            self.nodes.append({"node_id": n.get("node_id") or "", "meid": n.get("meid") or "",
                               "cu": f"{cu_base}/api/v0.1/CU/Logs/TelemetryExportReader/read",
                               # full KPM(322 鍵)快照。只經 E2 送 RIC 的話我方自己留不下來,
                               # 外部 Agent 的 I-5 原始觀測就給不出 cell 級量測鍵。
                               "pm": f"{cu_base}/api/v0.1/CU/E2/E2FullReporter/read",
                               "e2": e2, "cursor": {}, "control_seq": 0})
        # per-run UE driver(劇本時間);共用模式沒有
        self._ue = f"http://{ue_host}:8000/api/v0.1/UE/Scenario/ScenarioController/status" if ue_host else None
        # 2026-09-20:DU 的量測報告佇列滿了會丟最舊的,只寫在 DU log。資料悄悄變稀疏而
        # KPM 看起來完全正常(corridor_00_08 run 6:5× 下 3.5 分鐘丟 8,701 筆,每視窗
        # 只剩 4–12 個 UE 進統計)。接出來寫進 warnings,讓稀疏可見。
        self._du = f"http://{du_host}:8000/api/v0.1/DU/Tick/TickController/read" if du_host else None
        self._report_dropped = 0

    @property
    def control_seq(self) -> int:   # 舊介面(單 node)相容
        return self.nodes[0]["control_seq"] if self.nodes else 0

    # 啟動時先把游標推到「現在」,只封存本 run 開始後的資料(CU 表跨 run 累積)
    def prime(self) -> None:
        """啟動時把游標推到「現在」:只封存本 run 開始後的資料(CU 表跨 run 累積,已達千萬列)。"""
        for n in self.nodes:
            n["cursor"] = dict(_post(n["cu"], {"max_only": True})["data"]["cursor"])
        self._snapshot_pm()
        for n in self.nodes:
            try:
                if not n["e2"]:
                    raise LookupError("no e2adapter")
                e = _post(n["e2"], {}, timeout=5.0)["data"]
                n["control_seq"] = max([int(x.get("seq", 0)) for x in _control_items(e)] or [0])
            except Exception:  # noqa: BLE001
                n["control_seq"] = 0

    def _snapshot_pm(self) -> None:
        """full KPM 快照。**不是每個輪詢週期都抓** —— 單筆約 27 KB,2 秒一份的話
        1x 跑 8 小時就是 388 MB。對方要的彙整粒度是 60 秒,原始的逐秒觀測
        RunKpmSample 已經有,所以這裡預設 60 劇本秒一份(env PM_SNAPSHOT_EVERY_SEC)。
        多 gNB:每個 gNB 一列(node_id / meid 分開)。"""
        _snap_every = float(getattr(settings, "PM_SNAPSHOT_EVERY_SEC", 60.0)) * 1000.0
        _now_ms = self._last_scene_ms
        _due = (_now_ms is None or self._last_snap_ms is None
                or (_now_ms - self._last_snap_ms) >= _snap_every)
        if not _due:
            return
        for n in self.nodes:
            try:
                snap = _post(n["pm"], {}, timeout=10.0)["data"]
                if snap.get("pm"):
                    self._last_snap_ms = _now_ms
                    DB.create_entity(RunPmSnapshot, {**_stamp("run_pm_snapshot"),
                        "f_scene_run_uuid": self.run_uuid, "run_seq": self.run_seq, "ric_run": self.ric_run,
                        "at_sim_ms": self._last_scene_ms, "wall_time_ms": int(time.time() * 1000),
                        "node_id": n["node_id"], "meid": n["meid"],
                        # e2 區塊(逐 UE 量測)不存 —— RunKpmSample.per_ue 已有同樣的資料,
                        # 存兩份只是讓歸檔多長 12%
                        "pm": snap.get("pm") or {}, "e2": [],
                        "warnings": snap.get("warnings") or []})
                    self.stats["pm_snapshots"] = self.stats.get("pm_snapshots", 0) + 1
            except Exception:  # noqa: BLE001
                pass

    def stop(self) -> None:
        self._stop_evt.set()

    def run(self) -> None:
        try:
            self.prime()
        except Exception as exc:  # noqa: BLE001
            logger.warning("archiver prime failed run=%s: %s", self.run_uuid, exc)
        while not self._stop_evt.is_set():
            self._poll_once()
            self._stop_evt.wait(self.poll_sec)
        self._poll_once()   # 收尾再撈一次
        close_old_connections()
        logger.info("archiver done run=%s stats=%s", self.run_uuid, self.stats)

    def _poll_once(self) -> None:
        self.stats["polls"] += 1
        close_old_connections()
        meas: list[dict] = []; cells: list[dict] = []
        for n in self.nodes:
            try:
                d = _post(n["cu"], {"since": n["cursor"], "limit": 2000})["data"]
                n["cursor"] = d["cursor"]
                tag = {"node_id": n["node_id"], "meid": n["meid"]}
                for m in d["measurement"]:
                    meas.append({**m, **tag})
                for c in d["cell"]:
                    cells.append({**c, **tag})
                for h in d["handover"]:
                    DB.create_entity(RunHandoverEvent, {**_stamp("run_handover_event"), "f_scene_run_uuid": self.run_uuid, "run_seq": self.run_seq, "ric_run": self.ric_run,
                        "at_sim_ms": int(h.get("scene_sim_ms") or 0), "ue_id": h["ue_id"], "source_cell": h["source_cell"], "target_cell": h["target_cell"],
                        "outcome": str(h.get("status") or ""), **tag,
                        "detail": {k: h.get(k) for k in ("trigger", "failure_cause", "mro_class", "started_at", "completed_at", "id",
                                                         "ho_type", "amf_ue_ngap_id", "source_ncgi", "target_ncgi",
                                                         "ric_label", "ric_instance_id")}})
                    self.stats["handover"] += 1
                # 自主組態變更(非 RIC 觸發)。與 RIC 下來的控制共用 RunControlEvent,
                # 靠 source 前綴分開:son/* vs ric/* —— Agent 介面 I-7 的 origin 就是照這個判。
                for a in d.get("son") or []:
                    DB.create_entity(RunControlEvent, {**_stamp("run_control_event"), "f_scene_run_uuid": self.run_uuid,
                        "run_seq": self.run_seq, "ric_run": self.ric_run, **tag,
                        "at_sim_ms": self._last_scene_ms if self._last_scene_ms is not None else self.ticks_so_far * self.sim_dt_ms,
                        "source": f"son/{a.get('function') or 'unknown'}",
                        "action_type": f"{a.get('object_type')}_{a.get('action')}"[:32],
                        "target": str(a.get("object_id") or "")[:128], "outcome": "applied",
                        "landing_latency_ms": None, "detail": a})
                    self.stats["control"] += 1
                for r in d["rlf"]:
                    DB.create_entity(RunHandoverEvent, {**_stamp("run_handover_event"), "f_scene_run_uuid": self.run_uuid, "run_seq": self.run_seq, "ric_run": self.ric_run,
                        "at_sim_ms": int(r.get("scene_sim_ms") or 0), "ue_id": r["ue_id"], "source_cell": r["source_cell"], "target_cell": r.get("reestab_cell") or "",
                        "outcome": "RLF", **tag, "detail": {k: r.get(k) for k in ("source_pci", "sinr_at_rlf", "t310_ms", "reason", "reestab_pci", "id", "outcome")}})
                    self.stats["rlf"] += 1
            except Exception as exc:  # noqa: BLE001
                self.stats["errors"] += 1
                logger.warning("archiver CU poll failed run=%s node=%s: %s", self.run_uuid, n["node_id"] or "-", exc)
        try:
            scene_t = None
            if self._ue:
                try:
                    scene_t = float(_post(self._ue, {}, timeout=3.0)["data"].get("elapsed_sim_sec"))
                except Exception:  # noqa: BLE001 — 拿不到就留 null,不影響封存
                    scene_t = None
            self._archive_kpm(meas, cells, scene_t, self._poll_report_dropped())
        except Exception as exc:  # noqa: BLE001
            self.stats["errors"] += 1
            logger.warning("archiver KPM archive failed run=%s: %s", self.run_uuid, exc)
        # 2026-09-27:full KPM 快照以前只在啟動時抓一次(註解說每 60 劇本秒一份,但程式只在 prime 裡)
        self._snapshot_pm()
        for n in self.nodes:
            self._poll_control(n)

    def _poll_control(self, n: dict) -> None:
        try:
            if not n["e2"]:
                raise LookupError("no e2adapter")
            e = _post(n["e2"], {}, timeout=5.0)["data"]
            # 2026-09-23:adapter 的稽核列是「最新在最前」。以前照它的順序走,第一筆(最新 seq)就把
            # control_seq 推到最大,同一輪裡較舊的列全被當成「已歸檔」跳過 —— run 40 五筆只留兩筆。
            for x in sorted(_control_items(e), key=lambda r: int(r.get("seq", 0))):
                # adapter 的稽核列:command(sim action)/ result(落地目標,例 cell id)/ acked / rttMs / failure
                outcome = "ACK" if x.get("acked") else ("FAIL" if x.get("failure") else "pending")
                if int(x.get("seq", 0)) <= n["control_seq"]:
                    # 2026-09-23:已歸檔過的命令,ack/failure 常在下一次輪詢才到 → 補寫結果,
                    # 否則 I-7 永遠是 pending(RIC 對 2-6 的 ACK 我方就對不上)。
                    _row = (RunControlEvent.objects
                            .filter(f_scene_run_uuid=self.run_uuid, run_seq=self.run_seq, node_id=n["node_id"],
                                    source__startswith="ric/", detail__seq=x.get("seq")).first())
                    if _row is not None and _row.outcome != outcome:
                        _row.outcome = outcome; _row.detail = x
                        _row.target = str(x.get("result") or x.get("target") or "")[:128]
                        _row.run_control_event_updated_at = TimestampService.now()
                        _row.save(update_fields=["outcome", "detail", "target", "run_control_event_updated_at"])
                    continue
                n["control_seq"] = int(x.get("seq", 0))
                DB.create_entity(RunControlEvent, {**_stamp("run_control_event"), "f_scene_run_uuid": self.run_uuid, "run_seq": self.run_seq, "ric_run": self.ric_run,
                    "node_id": n["node_id"], "meid": n["meid"],
                    "at_sim_ms": self._last_scene_ms if self._last_scene_ms is not None else self.ticks_so_far * self.sim_dt_ms,
                    "source": f"ric/{x.get('ranFuncName') or 'RC'}",
                    "action_type": str(x.get("command") or x.get("kind") or "control")[:32],
                    "target": str(x.get("result") or x.get("target") or "")[:128], "outcome": outcome,
                    "landing_latency_ms": (int(round(float(x["rttMs"]))) if x.get("rttMs") is not None else None), "detail": x})
                self.stats["control"] += 1
        except Exception:  # noqa: BLE001 — E2Adapter/RIC 不通是常態,不算錯
            pass

    def _poll_report_dropped(self) -> int:
        """這一輪 DU 又丟了幾筆量測報告(累計值相減)。拿不到就回 0,不影響封存。"""
        if not self._du:
            return 0
        try:
            total = int((_post(self._du, {}, timeout=3.0)["data"] or {}).get("report_dropped") or 0)
        except Exception:  # noqa: BLE001
            return 0
        delta = max(0, total - self._report_dropped)
        self._report_dropped = total
        return delta

    def _archive_kpm(self, meas: list[dict], cells: list[dict], scene_t: float | None = None, dropped: int = 0) -> None:
        """同一 PM 視窗 → 一列 run_kpm_sample:per_ue + per_cell。

        2026-09-21:原本以 recorded_at 的「秒」為鍵,而 per_ue 是以 ue_id 為鍵的字典 ——
        2× 速度下每個 UE 每實際秒有兩份報告,後者直接覆蓋前者。實測 2,000 列原始量測
        依秒分組後只剩 1,066 列,**靜靜丟掉 47%**(RIC 端獨立看到我們的筆數只有他們的 65%)。
        改以 DU 帶來的 window_seq 分組;舊 DU 不帶就退回依秒(行為與從前相同)。
        """
        by_win: dict[str, dict] = defaultdict(lambda: {"per_ue": {}, "per_cell": {}, "tick": None, "scene_ms": None})
        for m in meas:
            ws = m.get("window_seq")
            w = f"w{ws}" if ws is not None else (m.get("recorded_at") or "")[:19]
            by_win[w]["per_ue"][m["ue_id"]] = {k: m.get(k) for k in ("serving_cell", "rsrp_dbm", "sinr_db", "throughput_dl_mbps", "throughput_ul_mbps",
                                                                    "mcs_dl", "rb_width_dl", "mimo_rank", "pdcp_sdu_volume_dl", "pdcp_sdu_volume_ul",
                                                                    "rlc_sdu_delay_dl_ms", "qos_5qi", "neighbor_cells_json",
                                                                    "mcs_ul", "rb_width_ul", "ul_sinr_db", "sinr_layers_json", "beam_id", "rsrq_db",
                                                                    "node_id", "meid")}
            if m.get("scene_sim_ms") is not None:
                by_win[w]["scene_ms"] = int(m["scene_sim_ms"])
        for c in cells:
            cws = c.get("window_seq")
            w = f"w{cws}" if cws is not None else (c.get("recorded_at") or "")[:19]
            by_win[w]["per_cell"][c["cell_id"]] = {k: c.get(k) for k in ("prb_pct_dl", "prb_pct_ul", "window_seconds", "connected_ues", "node_id", "meid")}
            # CU 是全域表,舊劇本殘留的 cell 會以 tick_count=0 出現在同一視窗;取視窗內最大值才是真的走了幾個 tick
            by_win[w]["tick"] = max(int(c.get("tick_count") or 0), int(by_win[w]["tick"] or 0))
            if c.get("scene_sim_ms") is not None:
                by_win[w]["scene_ms"] = int(c["scene_sim_ms"])
        # w<seq> 鍵要用數值排序 —— 字典序會讓 "w10" 排在 "w9" 前面,
        # window_index 與 scene_t 的回推就都錯了。
        def _wkey(k: str):
            return (0, int(k[1:])) if k.startswith("w") and k[1:].isdigit() else (1, k)

        wins = sorted(by_win, key=_wkey)
        # 同一輪可能封存多個視窗:最後一個對到 scene_t,較早的依 sim-time 差往回推
        tick_after = {w: sum(int(by_win[x]["tick"] or 0) for x in wins[i + 1:]) for i, w in enumerate(wins)}
        # 2026-09-21:歸檔每 poll_sec 輪詢一次,同一個 PM 視窗的報告常跨兩輪抵達,
        # 於是被寫成兩列互補的半截(實測 39 個不完整視窗中 36 個與鄰居相加剛好 18、
        # 且 UE 完全不重疊)。把每批「最新」的那個視窗留到下一輪再寫。
        carry = getattr(self, "_carry_win", None)
        if carry:
            ck, cv = carry
            if ck in by_win:      # 下一輪補齊了 → 併回來
                by_win[ck]["per_ue"] = {**cv["per_ue"], **by_win[ck]["per_ue"]}
                by_win[ck]["per_cell"] = {**cv["per_cell"], **by_win[ck]["per_cell"]}
                by_win[ck]["tick"] = max(int(cv["tick"] or 0), int(by_win[ck]["tick"] or 0)) or None
                by_win[ck]["scene_ms"] = by_win[ck].get("scene_ms") or cv.get("scene_ms")
            else:                 # 這一輪沒它了 → 視為已完整,寫出去
                by_win[ck] = cv
            self._carry_win = None
            wins = sorted(by_win, key=_wkey)
        if len(wins) > 1 and wins[-1].startswith("w"):
            self._carry_win = (wins[-1], by_win.pop(wins[-1]))
            wins = wins[:-1]
            tick_after = {w: sum(int(by_win[x]["tick"] or 0) for x in wins[i + 1:]) for i, w in enumerate(wins)}
        for w in wins:
            b = by_win[w]
            _merge_beam_stats(b["per_cell"], b["per_ue"], self._last_beam)
            tick = b["tick"]
            if tick is not None:
                self.ticks_so_far += int(tick)
            if b.get("scene_ms") is not None:
                self._last_scene_ms = int(b["scene_ms"])
            # 2026-09-22:同一個劇本秒已有列就**合併**,不再新增。
            # CU 過載時同一視窗的報告會跨兩次輪詢抵達(第一次寫了部分 UE,第二次剩下的 UE
            # 又被當成新視窗寫一列);carry 只保護每批最後一窗。實測 10x 一場 1800 s 有 4830 列、
            # 35% 的劇本秒重複,且拆掉 RU↔DU 互等後也沒變 —— 這是歸檔端的問題,在這裡收斂。
            _sim_ms = (b["scene_ms"] if b.get("scene_ms") is not None else self.ticks_so_far * self.sim_dt_ms)
            _exist = (RunKpmSample.objects
                      .filter(f_scene_run_uuid=self.run_uuid, run_seq=self.run_seq, sim_time_ms=_sim_ms)
                      .order_by("id").first()) if b.get("scene_ms") is not None else None
            if _exist is not None:
                _pu = dict(_exist.per_ue or {}); _pu.update(b["per_ue"] or {})
                _pc = dict(_exist.per_cell or {}); _pc.update(b["per_cell"] or {})
                _w = list(_exist.warnings or []) + [x for x in _win_warnings(b, tick) if x not in (_exist.warnings or [])]
                _exist.per_ue = _pu; _exist.per_cell = _pc; _exist.warnings = _w
                _exist.run_kpm_sample_updated_at = TimestampService.now()   # 欄位沒有 auto_now,要自己填
                _exist.save(update_fields=["per_ue", "per_cell", "warnings", "run_kpm_sample_updated_at"])
                self.stats["merged"] = self.stats.get("merged", 0) + 1
                continue
            DB.create_entity(RunKpmSample, {**_stamp("run_kpm_sample"), "f_scene_run_uuid": self.run_uuid, "run_seq": self.run_seq, "ric_run": self.ric_run,
                # 劇本時鐘優先。tick 累加只是舊 DU 的退路 —— 報告一掉就失真
                # (實測 8h 劇本一場少算 59%、另一場多算 12%)。
                "window_index": self.window_index,
                "sim_time_ms": (b["scene_ms"] if b.get("scene_ms") is not None
                                else self.ticks_so_far * self.sim_dt_ms),
                "wall_time_ms": int(time.time() * 1000), "per_cell": b["per_cell"],
                # 2026-09-22:scene_t_sec 改與 sim_time_ms 同源(DU 的劇本時鐘)。
                # 以前取 UE 的 elapsed_sim_sec —— 那是「牆鐘 × 設定倍速」的推算,
                # 倍速達不到時會嚴重高估(實測一場 DU 走 904s、UE 算成 3633s)。
                # 換手 / RLF 事件用的是 DU 的 scene_sim_ms,兩邊不同源的話
                # 外部 Agent 無法把觀測資料與事件對到同一條時間軸上。
                # 舊 DU 不帶 scene_sim_ms 時才退回原本的 UE 推算。
                "scene_t_sec": (round(b["scene_ms"] / 1000.0, 2) if b.get("scene_ms") is not None
                                else (None if scene_t is None
                                      else round(max(0.0, scene_t - tick_after[w] * self.sim_dt_ms / 1000.0), 2))),
                "per_ue": b["per_ue"], "warnings": _win_warnings(b, tick) + ([] if tick is not None else ["no cell row → sim_time unknown"])
                             + ([] if not (dropped and w == wins[-1]) else
                                [f"自上次封存以來 DU 丟棄量測報告 {dropped} 筆(CU 消化不及)→ 這段期間各視窗的 UE 可能不完整"])})
            self.window_index += 1
            self.stats["samples"] += 1


def beam_stats(per_ue: dict, last_beam: dict) -> dict:
    """每 cell 每波束的統計(O-RAN WG1 §4.6.4.1 每波束 KPI)+ 波束切換次數。

    回傳 {cell: {"beams": {beam_id: {ue_count, rsrp_avg_dbm, sinr_avg_db, sinr_min_db, prb_dl, thp_dl_mbps}},
                 "beam_switches": n}};沒有 beam_id(單埠 / Cat A 未設 GoB)的 UE 不計。
    last_beam 是 {ue: (cell, beam)},原地更新:同 cell 內 beam 變了才算一次切換(換 cell 算換手,不算)。
    """
    out: dict = {}
    for ue, v in per_ue.items():
        cell, beam = v.get("serving_cell") or "", v.get("beam_id")
        if not cell or beam is None:
            continue
        c = out.setdefault(cell, {"beams": {}, "beam_switches": 0})
        acc = c["beams"].setdefault(str(beam), {"ue_count": 0, "_rsrp": [], "_sinr": [], "prb_dl": 0, "thp_dl_mbps": 0.0})
        acc["ue_count"] += 1
        if isinstance(v.get("rsrp_dbm"), (int, float)):
            acc["_rsrp"].append(float(v["rsrp_dbm"]))
        if isinstance(v.get("sinr_db"), (int, float)) and v["sinr_db"] > -99:
            acc["_sinr"].append(float(v["sinr_db"]))
        acc["prb_dl"] += int(v.get("rb_width_dl") or 0)
        acc["thp_dl_mbps"] += float(v.get("throughput_dl_mbps") or 0.0)
        prev = last_beam.get(ue)
        if prev is not None and prev[0] == cell and prev[1] != beam:
            c["beam_switches"] += 1
        last_beam[ue] = (cell, beam)
    for c in out.values():
        for acc in c["beams"].values():
            r, q = acc.pop("_rsrp"), acc.pop("_sinr")
            acc["rsrp_avg_dbm"] = round(sum(r) / len(r), 2) if r else None
            acc["sinr_avg_db"] = round(sum(q) / len(q), 2) if q else None
            acc["sinr_min_db"] = round(min(q), 2) if q else None
            acc["thp_dl_mbps"] = round(acc["thp_dl_mbps"], 3)
    return out


def _win_warnings(b: dict, tick) -> list[str]:
    """空視窗該不該示警,看 cell 有沒有回報「本來就沒人掛著」。

    2026-09-21:走廊 00–08 前 4.8 小時劇本上一個人都不在場,那段的 KPM 本來就該是空的,
    以前卻一律標 no ue rows —— 17404 個視窗全變警告,監控頁一片紅,真正的報告遺失反而
    被淹沒。DU 現在會帶 connected_ues,兩種情況就分得開:
      cell 說掛著 0 個 UE  → 空是對的,不示警
      cell 說掛著 >0 個    → 有人卻沒量測,是真的遺失,示警
      沒有 connected_ues  → 舊版 DU,退回舊行為(一律示警)
    """
    if b["per_ue"]:
        return []
    counts = [c.get("connected_ues") for c in (b["per_cell"] or {}).values()]
    known = [n for n in counts if n is not None]
    if known and not any(known):
        return []
    return ["no ue rows"]


def _merge_beam_stats(per_cell: dict, per_ue: dict, last_beam: dict) -> None:
    for cell, st in beam_stats(per_ue, last_beam).items():
        per_cell.setdefault(cell, {}).update(st)


def current_run_seq(scene_run_uuid: str) -> int:
    """這個 run 目前歸檔到第幾次執行(沒有紀錄回 0)。"""
    from django.db.models import Max
    return int((RunKpmSample.objects.filter(f_scene_run_uuid=scene_run_uuid)
                .aggregate(m=Max("run_seq")).get("m")) or 0)


def active_run_seq(scene_run_uuid: str) -> int:
    """**正在跑**的那一輪的 run_seq —— 直接問 archiver thread。

    2026-09-22:不要用 current_run_seq() 代替。那支是從 RunKpmSample 取 max,
    而 archiver 剛啟動、還沒寫出第一個視窗時,max 仍是**上一輪**的號碼。
    外部 Agent 的事件紀錄若用到上一輪的號碼,I-7 依「最新 run_seq」過濾就會
    整批看不到這次注入的事件。archiver 還沒起來才退回資料庫的值。
    """
    t = _threads.get(scene_run_uuid)
    if t is not None and getattr(t, "run_seq", None):
        return int(t.run_seq)
    return current_run_seq(scene_run_uuid)


def current_ric_run(scene_run_uuid: str) -> int:
    """這個 run 最近一次記到的 RIC 場次號(沒有回 0)。orchestrator 重啟接回時用。"""
    from django.db.models import Max
    return int((RunKpmSample.objects.filter(f_scene_run_uuid=scene_run_uuid)
                .aggregate(m=Max("ric_run")).get("m")) or 0)


def start_archiver(scene_run_uuid: str, sim_dt_ms: int, cu_host: str | None = None, e2_port: int | None = None,
                   new_run: bool = True, ric_run: int = 0, nodes: list[dict] | None = None,
                   ue_host: str | None = None, du_host: str | None = None) -> RunArchiver:
    """new_run=True(一次 start)→ run_seq +1;False(orchestrator 重啟後接回)→ 沿用目前這次。
    ric_run:RIC 閘道宣告回應的 `run`;接回時沒有來源,沿用資料庫裡最近一次的值。"""
    with _lock:
        old = _threads.get(scene_run_uuid)
        if old and old.is_alive():
            return old
        seq = current_run_seq(scene_run_uuid)
        seq = seq + 1 if new_run else max(seq, 1)
        rr = int(ric_run) or (current_ric_run(scene_run_uuid) if not new_run else 0)
        t = RunArchiver(scene_run_uuid, sim_dt_ms, cu_host=cu_host, e2_port=e2_port, run_seq=seq, ric_run=rr,
                        nodes=nodes, ue_host=ue_host, du_host=du_host)
        logger.info("archiver run=%s run_seq=%d ric_run=%d(%s)", scene_run_uuid, seq, rr, "新一次執行" if new_run else "接回")
        _threads[scene_run_uuid] = t
        t.start()
        return t


def stop_archiver(scene_run_uuid: str, join_sec: float = 10.0) -> dict | None:
    with _lock:
        t = _threads.pop(scene_run_uuid, None)
    if t is None:
        return None
    t.stop(); t.join(join_sec)
    return t.stats
