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
    def __init__(self, scene_run_uuid: str, sim_dt_ms: int, poll_sec: float = 2.0, cu_host: str | None = None, e2_port: int | None = None, run_seq: int = 0, ric_run: int = 0) -> None:
        super().__init__(name=f"archiver-{scene_run_uuid[-8:]}", daemon=True)
        self.run_uuid = scene_run_uuid
        self.run_seq = int(run_seq)
        # RIC 閘道的場次號(宣告回應的 `run`);宣告失敗或還沒回來時是 0
        self.ric_run = int(ric_run)
        self.sim_dt_ms = max(1, int(sim_dt_ms))
        self.poll_sec = poll_sec
        self._stop_evt = threading.Event()   # 不可叫 _stop:會蓋掉 Thread._stop() 讓 join() 炸
        self.cursor: dict[str, int] = {}
        self.control_seq = 0
        # 同一 run 若被再次 start,接在既有視窗後面,不從 0 重算(否則 window_index / sim_time 重複)
        last = RunKpmSample.objects.filter(f_scene_run_uuid=scene_run_uuid).order_by("-window_index").first()
        self.window_index = (last.window_index + 1) if last else 0
        self.ticks_so_far = (last.sim_time_ms // self.sim_dt_ms) if last else 0   # CellMeasurementLog.tick_count 是「窗內 tick 數」,累計才是 sim-time
        self._last_beam: dict = {}   # ue → (cell, beam_id),算波束切換次數
        self.stats = {"samples": 0, "handover": 0, "rlf": 0, "control": 0, "polls": 0, "errors": 0}
        self._cu = f"http://{cu_host or settings.HTTP_CU_HOST}:{8000 if cu_host else settings.HTTP_CU_PORT}/api/v0.1/CU/Logs/TelemetryExportReader/read"   # per-run CU(P4-1)或共用 CU
        # per-run UE driver(劇本時間);共用模式沒有
        self._ue = (f"http://{cu_host.replace('cu-', 'ue-', 1)}:8000/api/v0.1/UE/Scenario/ScenarioController/status"
                    if cu_host and cu_host.startswith("cu-") else None)
        self._e2 = f"http://{settings.HTTP_E2ADAPTER_HOST}:{e2_port or settings.HTTP_E2ADAPTER_PORT}/api/v0.1/E2Adapter/ControlAudit/ControlAuditReader/read"   # per-run adapter(P4-2)或共用

    # 啟動時先把游標推到「現在」,只封存本 run 開始後的資料(CU 表跨 run 累積)
    def prime(self) -> None:
        """啟動時把游標推到「現在」:只封存本 run 開始後的資料(CU 表跨 run 累積,已達千萬列)。"""
        self.cursor = dict(_post(self._cu, {"max_only": True})["data"]["cursor"])
        try:
            e = _post(self._e2, {}, timeout=5.0)["data"]
            self.control_seq = max([int(x.get("seq", 0)) for x in _control_items(e)] or [0])
        except Exception:  # noqa: BLE001
            self.control_seq = 0

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
        try:
            close_old_connections()
            d = _post(self._cu, {"since": self.cursor, "limit": 2000})["data"]
            self.cursor = d["cursor"]
            scene_t = None
            if self._ue:
                try:
                    scene_t = float(_post(self._ue, {}, timeout=3.0)["data"].get("elapsed_sim_sec"))
                except Exception:  # noqa: BLE001 — 拿不到就留 null,不影響封存
                    scene_t = None
            self._archive_kpm(d["measurement"], d["cell"], scene_t)
            for h in d["handover"]:
                DB.create_entity(RunHandoverEvent, {**_stamp("run_handover_event"), "f_scene_run_uuid": self.run_uuid, "run_seq": self.run_seq, "ric_run": self.ric_run,
                    "at_sim_ms": 0, "ue_id": h["ue_id"], "source_cell": h["source_cell"], "target_cell": h["target_cell"],
                    "outcome": str(h.get("status") or ""), "detail": {k: h.get(k) for k in ("trigger", "failure_cause", "mro_class", "started_at", "completed_at", "id")}})
                self.stats["handover"] += 1
            for r in d["rlf"]:
                DB.create_entity(RunHandoverEvent, {**_stamp("run_handover_event"), "f_scene_run_uuid": self.run_uuid, "run_seq": self.run_seq, "ric_run": self.ric_run,
                    "at_sim_ms": 0, "ue_id": r["ue_id"], "source_cell": r["source_cell"], "target_cell": r.get("reestab_cell") or "",
                    "outcome": "RLF", "detail": {k: r.get(k) for k in ("source_pci", "sinr_at_rlf", "t310_ms", "reason", "reestab_pci", "id")}})
                self.stats["rlf"] += 1
        except Exception as exc:  # noqa: BLE001
            self.stats["errors"] += 1
            logger.warning("archiver CU poll failed run=%s: %s", self.run_uuid, exc)
        try:
            e = _post(self._e2, {}, timeout=5.0)["data"]
            for x in _control_items(e):
                if int(x.get("seq", 0)) <= self.control_seq:
                    continue
                self.control_seq = int(x.get("seq", 0))
                # adapter 的稽核列:command(sim action)/ result(落地目標,例 cell id)/ acked / rttMs / failure
                outcome = "ACK" if x.get("acked") else ("FAIL" if x.get("failure") else "pending")
                DB.create_entity(RunControlEvent, {**_stamp("run_control_event"), "f_scene_run_uuid": self.run_uuid, "run_seq": self.run_seq, "ric_run": self.ric_run,
                    "at_sim_ms": self.ticks_so_far * self.sim_dt_ms, "source": f"ric/{x.get('ranFuncName') or 'RC'}",
                    "action_type": str(x.get("command") or x.get("kind") or "control")[:32],
                    "target": str(x.get("result") or x.get("target") or "")[:128], "outcome": outcome,
                    "landing_latency_ms": (int(round(float(x["rttMs"]))) if x.get("rttMs") is not None else None), "detail": x})
                self.stats["control"] += 1
        except Exception:  # noqa: BLE001 — E2Adapter/RIC 不通是常態,不算錯
            pass

    def _archive_kpm(self, meas: list[dict], cells: list[dict], scene_t: float | None = None) -> None:
        """同一 PM 視窗(recorded_at 秒)→ 一列 run_kpm_sample:per_ue + per_cell。"""
        by_win: dict[str, dict] = defaultdict(lambda: {"per_ue": {}, "per_cell": {}, "tick": None})
        for m in meas:
            w = (m.get("recorded_at") or "")[:19]
            by_win[w]["per_ue"][m["ue_id"]] = {k: m.get(k) for k in ("serving_cell", "rsrp_dbm", "sinr_db", "throughput_dl_mbps", "throughput_ul_mbps",
                                                                    "mcs_dl", "rb_width_dl", "mimo_rank", "pdcp_sdu_volume_dl", "pdcp_sdu_volume_ul",
                                                                    "rlc_sdu_delay_dl_ms", "qos_5qi", "neighbor_cells_json",
                                                                    "mcs_ul", "rb_width_ul", "ul_sinr_db", "sinr_layers_json", "beam_id")}
        for c in cells:
            w = (c.get("recorded_at") or "")[:19]
            by_win[w]["per_cell"][c["cell_id"]] = {k: c.get(k) for k in ("prb_pct_dl", "prb_pct_ul", "window_seconds")}
            # CU 是全域表,舊劇本殘留的 cell 會以 tick_count=0 出現在同一視窗;取視窗內最大值才是真的走了幾個 tick
            by_win[w]["tick"] = max(int(c.get("tick_count") or 0), int(by_win[w]["tick"] or 0))
        wins = sorted(by_win)
        # 同一輪可能封存多個視窗:最後一個對到 scene_t,較早的依 sim-time 差往回推
        tick_after = {w: sum(int(by_win[x]["tick"] or 0) for x in wins[i + 1:]) for i, w in enumerate(wins)}
        for w in wins:
            b = by_win[w]
            _merge_beam_stats(b["per_cell"], b["per_ue"], self._last_beam)
            tick = b["tick"]
            if tick is not None:
                self.ticks_so_far += int(tick)
            DB.create_entity(RunKpmSample, {**_stamp("run_kpm_sample"), "f_scene_run_uuid": self.run_uuid, "run_seq": self.run_seq, "ric_run": self.ric_run,
                "window_index": self.window_index, "sim_time_ms": self.ticks_so_far * self.sim_dt_ms,
                "wall_time_ms": int(time.time() * 1000), "per_cell": b["per_cell"],
                "scene_t_sec": (None if scene_t is None else round(max(0.0, scene_t - tick_after[w] * self.sim_dt_ms / 1000.0), 2)), "per_ue": b["per_ue"], "warnings": ([] if b["per_ue"] else ["no ue rows"]) + ([] if tick is not None else ["no cell row → sim_time unknown"])})
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


def _merge_beam_stats(per_cell: dict, per_ue: dict, last_beam: dict) -> None:
    for cell, st in beam_stats(per_ue, last_beam).items():
        per_cell.setdefault(cell, {}).update(st)


def current_run_seq(scene_run_uuid: str) -> int:
    """這個 run 目前歸檔到第幾次執行(沒有紀錄回 0)。"""
    from django.db.models import Max
    return int((RunKpmSample.objects.filter(f_scene_run_uuid=scene_run_uuid)
                .aggregate(m=Max("run_seq")).get("m")) or 0)


def current_ric_run(scene_run_uuid: str) -> int:
    """這個 run 最近一次記到的 RIC 場次號(沒有回 0)。orchestrator 重啟接回時用。"""
    from django.db.models import Max
    return int((RunKpmSample.objects.filter(f_scene_run_uuid=scene_run_uuid)
                .aggregate(m=Max("ric_run")).get("m")) or 0)


def start_archiver(scene_run_uuid: str, sim_dt_ms: int, cu_host: str | None = None, e2_port: int | None = None,
                   new_run: bool = True, ric_run: int = 0) -> RunArchiver:
    """new_run=True(一次 start)→ run_seq +1;False(orchestrator 重啟後接回)→ 沿用目前這次。
    ric_run:RIC 閘道宣告回應的 `run`;接回時沒有來源,沿用資料庫裡最近一次的值。"""
    with _lock:
        old = _threads.get(scene_run_uuid)
        if old and old.is_alive():
            return old
        seq = current_run_seq(scene_run_uuid)
        seq = seq + 1 if new_run else max(seq, 1)
        rr = int(ric_run) or (current_ric_run(scene_run_uuid) if not new_run else 0)
        t = RunArchiver(scene_run_uuid, sim_dt_ms, cu_host=cu_host, e2_port=e2_port, run_seq=seq, ric_run=rr)
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
