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
    def __init__(self, scene_run_uuid: str, sim_dt_ms: int, poll_sec: float = 2.0, cu_host: str | None = None, e2_port: int | None = None) -> None:
        super().__init__(name=f"archiver-{scene_run_uuid[-8:]}", daemon=True)
        self.run_uuid = scene_run_uuid
        self.sim_dt_ms = max(1, int(sim_dt_ms))
        self.poll_sec = poll_sec
        self._stop_evt = threading.Event()   # 不可叫 _stop:會蓋掉 Thread._stop() 讓 join() 炸
        self.cursor: dict[str, int] = {}
        self.control_seq = 0
        # 同一 run 若被再次 start,接在既有視窗後面,不從 0 重算(否則 window_index / sim_time 重複)
        last = RunKpmSample.objects.filter(f_scene_run_uuid=scene_run_uuid).order_by("-window_index").first()
        self.window_index = (last.window_index + 1) if last else 0
        self.ticks_so_far = (last.sim_time_ms // self.sim_dt_ms) if last else 0   # CellMeasurementLog.tick_count 是「窗內 tick 數」,累計才是 sim-time
        self.stats = {"samples": 0, "handover": 0, "rlf": 0, "control": 0, "polls": 0, "errors": 0}
        self._cu = f"http://{cu_host or settings.HTTP_CU_HOST}:{8000 if cu_host else settings.HTTP_CU_PORT}/api/v0.1/CU/Logs/TelemetryExportReader/read"   # per-run CU(P4-1)或共用 CU
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
            self._archive_kpm(d["measurement"], d["cell"])
            for h in d["handover"]:
                DB.create_entity(RunHandoverEvent, {**_stamp("run_handover_event"), "f_scene_run_uuid": self.run_uuid,
                    "at_sim_ms": 0, "ue_id": h["ue_id"], "source_cell": h["source_cell"], "target_cell": h["target_cell"],
                    "outcome": str(h.get("status") or ""), "detail": {k: h.get(k) for k in ("trigger", "failure_cause", "mro_class", "started_at", "completed_at", "id")}})
                self.stats["handover"] += 1
            for r in d["rlf"]:
                DB.create_entity(RunHandoverEvent, {**_stamp("run_handover_event"), "f_scene_run_uuid": self.run_uuid,
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
                DB.create_entity(RunControlEvent, {**_stamp("run_control_event"), "f_scene_run_uuid": self.run_uuid,
                    "at_sim_ms": self.ticks_so_far * self.sim_dt_ms, "source": f"ric/{x.get('ranFuncName') or 'RC'}",
                    "action_type": str(x.get("command") or x.get("kind") or "control")[:32],
                    "target": str(x.get("result") or x.get("target") or "")[:128], "outcome": outcome,
                    "landing_latency_ms": (int(round(float(x["rttMs"]))) if x.get("rttMs") is not None else None), "detail": x})
                self.stats["control"] += 1
        except Exception:  # noqa: BLE001 — E2Adapter/RIC 不通是常態,不算錯
            pass

    def _archive_kpm(self, meas: list[dict], cells: list[dict]) -> None:
        """同一 PM 視窗(recorded_at 秒)→ 一列 run_kpm_sample:per_ue + per_cell。"""
        by_win: dict[str, dict] = defaultdict(lambda: {"per_ue": {}, "per_cell": {}, "tick": None})
        for m in meas:
            w = (m.get("recorded_at") or "")[:19]
            by_win[w]["per_ue"][m["ue_id"]] = {k: m.get(k) for k in ("serving_cell", "rsrp_dbm", "sinr_db", "throughput_dl_mbps", "throughput_ul_mbps",
                                                                    "mcs_dl", "rb_width_dl", "mimo_rank", "pdcp_sdu_volume_dl", "pdcp_sdu_volume_ul",
                                                                    "rlc_sdu_delay_dl_ms", "qos_5qi", "neighbor_cells_json",
                                                                    "mcs_ul", "rb_width_ul", "ul_sinr_db", "sinr_layers_json")}
        for c in cells:
            w = (c.get("recorded_at") or "")[:19]
            by_win[w]["per_cell"][c["cell_id"]] = {k: c.get(k) for k in ("prb_pct_dl", "prb_pct_ul", "window_seconds")}
            # CU 是全域表,舊劇本殘留的 cell 會以 tick_count=0 出現在同一視窗;取視窗內最大值才是真的走了幾個 tick
            by_win[w]["tick"] = max(int(c.get("tick_count") or 0), int(by_win[w]["tick"] or 0))
        for w in sorted(by_win):
            b = by_win[w]
            tick = b["tick"]
            if tick is not None:
                self.ticks_so_far += int(tick)
            DB.create_entity(RunKpmSample, {**_stamp("run_kpm_sample"), "f_scene_run_uuid": self.run_uuid,
                "window_index": self.window_index, "sim_time_ms": self.ticks_so_far * self.sim_dt_ms,
                "wall_time_ms": int(time.time() * 1000), "per_cell": b["per_cell"], "per_ue": b["per_ue"], "warnings": ([] if b["per_ue"] else ["no ue rows"]) + ([] if tick is not None else ["no cell row → sim_time unknown"])})
            self.window_index += 1
            self.stats["samples"] += 1


def start_archiver(scene_run_uuid: str, sim_dt_ms: int, cu_host: str | None = None, e2_port: int | None = None) -> RunArchiver:
    with _lock:
        old = _threads.get(scene_run_uuid)
        if old and old.is_alive():
            return old
        t = RunArchiver(scene_run_uuid, sim_dt_ms, cu_host=cu_host, e2_port=e2_port)
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
