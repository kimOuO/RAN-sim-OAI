"""事件排程器(介面 I-3)—— 依**劇本時鐘**在指定秒數觸發事件。

為什麼不能用牆鐘:對方給的 at_offset_s 是「自模擬起點的秒數」,而我方支援倍速。
30 倍速下牆鐘 12 秒就是劇本 360 秒,用牆鐘排程會差兩個數量級。
而且倍速的達成率不穩定(實測設 30× 只達成 27.3×),連換算都不可靠 ——
所以一律讀 DU 的 scene_sim_ms,那是 cached 通道查表與 KPM 視窗用的同一條時鐘。

觸發語意:
    劇本時鐘一旦「越過」事件的 at_offset_s 就觸發,而且只觸發一次。
    輪詢間隔內時鐘可能跳過好幾秒(高倍速),所以用「越過」而不是「等於」;
    落後多少秒一併記進 landing_latency_ms,對方看得到準不準。

失敗處理:執行失敗**不重試**,但一定落紀錄(outcome=failed)。
重試會讓事件發生時間偏離對方存檔的正確答案,反而更糟。
"""
from __future__ import annotations

import json
import threading
import urllib.request
from typing import Any

from django.utils import timezone

from main.apps.agent_api.services.optional import scenario_events
from main.apps.run_lifecycle.services.optional import health_monitor
from main.apps.run_telemetry_archive.models.run_control_event import RunControlEvent
from main.utils.logger import get_logger

logger = get_logger(__name__)

POLL_SEC = 1.0          # 輪詢間隔(牆鐘)。1 秒在 30 倍速下 ≈ 劇本 30 秒的解析度
_lock = threading.Lock()
_threads: dict[str, "EventScheduler"] = {}


def _uuid(run_uuid: str, event_id: str) -> str:
    return f"run_control_event-{run_uuid[-12:]}-{event_id}"[:255]


def _record(run_uuid: str, run_seq: int, at_sim_ms: int, ev: dict,
            outcome: str, result: dict, latency_ms: int | None) -> None:
    """落 RunControlEvent —— 對方由 I-7 取回,用來核對事件有沒有照他給的時間發生。

    source 前綴 agent/ 會讓 I-7 把它歸為 triggered_event(我方注入),
    與 son/*(我方自主行為)分得開 —— 那正是 I-7 存在的唯一理由。
    """
    now = timezone.now()
    try:
        RunControlEvent.objects.update_or_create(
            run_control_event_uuid=_uuid(run_uuid, ev["event_id"]),
            defaults={
                "f_scene_run_uuid": run_uuid,
                "run_seq": run_seq,
                "at_sim_ms": int(at_sim_ms),
                "source": f"agent/{ev['type']}",
                "action_type": ev["type"],
                "target": str(ev.get("target") or "")[:128],
                "outcome": outcome,
                "landing_latency_ms": latency_ms,
                "detail": {
                    "event_id": ev["event_id"],
                    "requested_at_offset_s": ev["at_offset_s"],
                    "params": ev.get("params") or {},
                    "mode": ev.get("mode"),
                    "result": result,
                    "object_type": "neighbour_relation" if ev["type"] == "relation_change" else "cell",
                    "revert_of": ev.get("_revert_of"),
                },
                "run_control_event_created_at": now,
                "run_control_event_updated_at": now,
            },
        )
    except Exception:  # noqa: BLE001 — 紀錄失敗不該連帶讓後面的事件停擺
        logger.exception("事件紀錄寫入失敗 run=%s event=%s", run_uuid, ev.get("event_id"))


class EventScheduler(threading.Thread):
    def __init__(self, run_uuid: str, events: list[dict], hosts: dict[str, str],
                 run_seq: int = 0, deadline_s: float | None = None) -> None:
        super().__init__(name=f"events-{run_uuid[-8:]}", daemon=True)
        self.run_uuid = run_uuid
        self.hosts = hosts
        self.run_seq = run_seq
        self.deadline_s = deadline_s
        self.events = sorted(events, key=lambda e: (e["at_offset_s"], e["event_id"]))
        self._stop_evt = threading.Event()
        self._fired: set[str] = set()

    def stop(self) -> None:
        self._stop_evt.set()

    @property
    def pending(self) -> int:
        return len(self.events) - len(self._fired)

    def _fire(self, ev: dict, now_s: float) -> None:
        latency_ms = int(max(0.0, now_s - float(ev["at_offset_s"])) * 1000)
        execer = scenario_events.EXECUTORS.get(ev["type"])
        if execer is None:
            _record(self.run_uuid, self.run_seq, int(now_s * 1000), ev, "failed",
                    {"error": f"沒有 {ev['type']} 的執行器"}, latency_ms)
            return
        try:
            result = execer(ev, self.hosts)
        except Exception as exc:  # noqa: BLE001
            logger.exception("事件執行失敗 %s %s", self.run_uuid, ev["event_id"])
            result = {"applied": False, "error": f"{type(exc).__name__}: {exc}"}
        outcome = "applied" if result.get("applied") else "failed"
        logger.info("事件 %s [%s] target=%s @劇本 %.1fs(誤差 %dms)→ %s",
                    ev["event_id"], ev["type"], ev.get("target"),
                    now_s, latency_ms, outcome)
        _record(self.run_uuid, self.run_seq, int(now_s * 1000), ev, outcome, result, latency_ms)

    def _stop_run(self, now_s: float) -> None:
        """劇本時鐘到達對方要求的 duration_s → 收工。

        我方既有的自動停止看的是**劇本自身的長度**(走廊劇本 8 小時),
        對方要的 600 秒不在那條路上。不在這裡收,對方輪詢 I-4 會等 8 小時,
        而且拿到的觀測資料遠超出他要的區間。
        """
        logger.info("run %s 達到 I-3 指定的 duration_s=%.0f(劇本時鐘 %.1fs)→ 停止",
                    self.run_uuid, self.deadline_s or 0, now_s)
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8000/api/v0.1/Run_orchestrator/Run_lifecycle/LaunchController/stop",
                data=json.dumps({"scene_run_uuid": self.run_uuid}).encode(),
                headers={"content-type": "application/json"})
            urllib.request.urlopen(req, timeout=180).read()
        except Exception:  # noqa: BLE001
            logger.exception("依 duration_s 停止 run 失敗 %s", self.run_uuid)

    def run(self) -> None:  # noqa: D102
        du = self.hosts.get("du")
        if not du or (not self.events and self.deadline_s is None):
            return
        logger.info("事件排程器啟動 run=%s 共 %d 筆,deadline=%s s",
                    self.run_uuid, len(self.events), self.deadline_s)
        while not self._stop_evt.is_set():
            try:
                now_s = health_monitor.scene_progress_sec(du)
                if now_s is not None:
                    for ev in self.events:
                        if ev["event_id"] in self._fired:
                            continue
                        if now_s + 1e-9 < float(ev["at_offset_s"]):
                            break          # 已排序,後面的只會更晚
                        self._fired.add(ev["event_id"])
                        self._fire(ev, now_s)
                    if self.deadline_s is not None and now_s >= float(self.deadline_s):
                        self._stop_run(now_s)
                        return
                    if self.pending == 0 and self.deadline_s is None:
                        logger.info("事件排程器完成 run=%s(全部 %d 筆已觸發)",
                                    self.run_uuid, len(self.events))
                        return
            except Exception as exc:  # noqa: BLE001
                logger.warning("事件輪詢 %s: %s", self.run_uuid, exc)
            self._stop_evt.wait(POLL_SEC)


def start(run_uuid: str, events: list[dict], hosts: dict[str, str], run_seq: int = 0,
          deadline_s: float | None = None) -> int:
    """啟動該 run 的事件排程。回傳排入的事件數(含自動補的還原動作)。

    deadline_s 是對方經 I-3 指定的 duration_s —— 沒有事件的類型一也要這個守門,
    否則會一路跑到劇本自身的長度。
    """
    if not events and deadline_s is None:
        return 0
    with _lock:
        old = _threads.get(run_uuid)
        if old and old.is_alive():
            old.stop()
        t = EventScheduler(run_uuid, events, hosts, run_seq, deadline_s)
        _threads[run_uuid] = t
        t.start()
    # 先把「已排程」落成紀錄,觸發時再更新為 applied/failed。
    # 這樣 orchestrator 中途重啟也看得出「本來要發生什麼」—— 對方存的是我方的
    # 請求當正確答案,少掉一筆就對不上,而「排了但沒觸發」本身就是重要資訊。
    for ev in events:
        _record(run_uuid, run_seq, int(float(ev["at_offset_s"]) * 1000), ev,
                "scheduled", {"applied": None}, None)
    return len(events)


def stop(run_uuid: str) -> None:
    with _lock:
        t = _threads.pop(run_uuid, None)
    if t:
        t.stop()
        t.join(3)


def status(run_uuid: str) -> dict[str, Any] | None:
    """給 I-4 附在狀態裡 —— 對方輪詢時看得到還有幾筆沒觸發。"""
    t = _threads.get(run_uuid)
    if not t:
        return None
    return {"total": len(t.events), "pending": t.pending, "alive": t.is_alive(),
            "deadline_s": t.deadline_s}


def resume(run_uuid: str, run_seq: int, hosts: dict[str, str]) -> int:
    """orchestrator 重啟後接回該 run 尚未觸發的事件。

    排程器是 in-process thread,orchestrator 一重啟就沒了,但 per-run 容器還在跑。
    沒有這支的話,對方排在後面的事件永遠不會發生 —— 而他存的正確答案裡有那些事件,
    整份題目的答案就是錯的。

    還原依據是啟動時就落下的 outcome='scheduled' 紀錄:它帶著原始的型別、目標、
    時間與參數,足以重建排程。已經觸發過的(applied/failed)不會被重排 ——
    _uuid() 以 event_id 為鍵,重複觸發會覆蓋掉真實的觸發時間。
    """
    rows = list(RunControlEvent.objects
                .filter(f_scene_run_uuid=run_uuid, run_seq=run_seq,
                        source__startswith="agent/", outcome="scheduled")
                .order_by("at_sim_ms"))
    if not rows:
        return 0
    events = []
    for r in rows:
        d = r.detail or {}
        events.append({
            "event_id": d.get("event_id") or r.run_control_event_uuid.rsplit("-", 1)[-1],
            "type": r.action_type,
            "target": r.target,
            "at_offset_s": float(d.get("requested_at_offset_s", r.at_sim_ms / 1000.0)),
            "duration_s": None,          # 還原動作啟動時就已經展開成獨立事件了
            "params": d.get("params") or {},
            "mode": d.get("mode") or "cached",
            "_revert_of": d.get("revert_of"),
        })
    logger.info("接回事件排程 run=%s 尚未觸發 %d 筆", run_uuid, len(events))
    with _lock:
        old = _threads.get(run_uuid)
        if old and old.is_alive():
            old.stop()
        t = EventScheduler(run_uuid, events, hosts, run_seq)
        _threads[run_uuid] = t
        t.start()
    return len(events)
