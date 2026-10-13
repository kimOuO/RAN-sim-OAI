"""全場鎖步時鐘(2026-09-27 多 gNB D1)。

一場裡每個 DU 是獨立容器;若各自計時就會漂移,而跨 cell 干擾需要「同一拍」所有 cell 的負載。
所以時鐘放在 RU(空中介面本來就是全場共用的一個),每一拍:

  1. 平行呼叫每個 DU 的 TickController/step(帶上一拍全場負載 + 屬於它的 UE 的量測)
  2. 收齊各 DU 的 DL TTI,合併成一份(PDU 串接、各 cell 負載聯集)
  3. 用合併後的 TTI 跑一次 dl_tti_pipeline —— 全場 UE、全場干擾一次算完
  4. 量測依 UE 所屬 DU 分好,下一拍帶回去;劇本時鐘 +sim_dt

量測晚一拍套用,與改版前「DU 非同步送 dl_tti、從回應本體套用 CQI」相同。
DU 必須以 SIM_CLOCK=external 啟動;RU 必須單一 process(gunicorn 1 worker),否則時鐘會有兩份。
"""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests
from django.conf import settings

from main.utils.logger import get_logger

logger = get_logger(__name__)

_STEP_PATH = "/api/v0.1/DU/Tick/TickController/step"
_STEP_TIMEOUT_SEC = float(os.environ.get("RU_CLOCK_STEP_TIMEOUT_SEC", "10") or 10)


def du_urls_from_env() -> list[str]:
    """DU 端點:拓樸(RUN_TOPOLOGY)> RU_DU_URLS(逗號分隔)> 單一 HTTP_DU_HOST(舊)。"""
    try:
        from ran_sim_protocol.run_topology import RunTopology
        topo = RunTopology.from_env()
    except Exception:  # noqa: BLE001 — 舊 protocol 套件沒有 run_topology
        topo = None
    if topo is not None:
        return [d.url for d in topo.dus()]
    raw = (os.environ.get("RU_DU_URLS") or "").strip()
    if raw:
        return [u.strip().rstrip("/") for u in raw.split(",") if u.strip()]
    return [f"http://{settings.HTTP_DU_HOST}:{settings.HTTP_DU_PORT}"]


def merge_dl_tti(parts: list[dict[str, Any]], scene_sim_ms: int) -> dict[str, Any] | None:
    """各 DU 的 DL TTI(已編碼 dict)→ 一份全場的。沒有任何 DU 回 TTI 時回 None。"""
    parts = [p for p in parts if p]
    if not parts:
        return None
    merged: dict[str, Any] = {"sfn": int(parts[0].get("sfn", 0)), "slot": int(parts[0].get("slot", 0)),
                              "pdus": [], "cell_ul_load": {}, "cell_dl_load": {}, "scene_sim_ms": int(scene_sim_ms)}
    for p in parts:
        merged["pdus"].extend(p.get("pdus") or [])
        merged["cell_ul_load"].update(p.get("cell_ul_load") or {})
        merged["cell_dl_load"].update(p.get("cell_dl_load") or {})
    return merged


class LockstepClock:
    def __init__(self, du_urls: list[str] | None = None):
        self._du_urls = list(du_urls) if du_urls is not None else None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sessions: dict[str, requests.Session] = {}
        self._pool: ThreadPoolExecutor | None = None
        self.reset(sim_dt_ms=500, speed_x=1.0)

    # ── 狀態 ────────────────────────────────────────────────
    def reset(self, *, sim_dt_ms: int, speed_x: float) -> None:
        self.tick = 0
        self.scene_origin = 0
        self.sim_dt_ms = max(10, min(500, int(sim_dt_ms)))
        self.speed_x = max(0.01, float(speed_x))
        self.global_dl_load: dict[str, float] = {}
        self.pending: dict[str, list[dict[str, Any]]] = {}   # du_url → 下一拍要帶回的量測
        self.step_errors = 0
        self.last_error = ""
        self.achieved_speed_x = 0.0
        self.body_ms = {"avg": 0.0, "max": 0.0}
        self._acc: list[float] = []
        self._win = (0.0, 0)

    @property
    def du_urls(self) -> list[str]:
        if self._du_urls is None:
            self._du_urls = du_urls_from_env()
        return self._du_urls

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    @property
    def scene_tick(self) -> int:
        return max(0, self.tick - self.scene_origin)

    def status(self) -> dict[str, Any]:
        return {"running": self.running, "tick": self.tick, "scene_tick": self.scene_tick,
                "scene_sim_ms": self.scene_tick * self.sim_dt_ms, "sim_dt_ms": self.sim_dt_ms,
                "speed_x": self.speed_x, "sim_speed_x": self.speed_x,
                "wall_tick_ms": round(self.sim_dt_ms / self.speed_x, 2),
                "achieved_speed_x": self.achieved_speed_x, "body_ms": dict(self.body_ms),
                "du_urls": list(self.du_urls), "step_errors": self.step_errors, "last_error": self.last_error}

    # ── 控制 ────────────────────────────────────────────────
    def start(self, *, sim_dt_ms: int = 500, speed_x: float = 1.0) -> bool:
        with self._lock:
            if self.running:
                return False
            self.reset(sim_dt_ms=sim_dt_ms, speed_x=speed_x)
            self._stop.clear()
            self._pool = ThreadPoolExecutor(max_workers=max(1, len(self.du_urls)), thread_name_prefix="ru-clock-du")
            self._thread = threading.Thread(target=self._loop, name="ru-lockstep-clock", daemon=True)
            self._thread.start()
            logger.info("lockstep clock started: %d DU, sim_dt=%d ms, speed=%.2fx", len(self.du_urls), self.sim_dt_ms, self.speed_x)
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self.running:
                return False
            self._stop.set()
        th = self._thread
        if th is not None:
            th.join(timeout=_STEP_TIMEOUT_SEC + 5)
        if self._pool is not None:
            self._pool.shutdown(wait=False)
            self._pool = None
        logger.info("lockstep clock stopped at tick %d", self.tick)
        return True

    def set_speed(self, speed_x: float, sim_dt_ms: int | None = None) -> None:
        self.speed_x = max(0.01, float(speed_x))
        if sim_dt_ms:
            self.sim_dt_ms = max(10, min(500, int(sim_dt_ms)))

    def align_scene(self) -> int:
        """劇本從下一拍起算(UE 軌跡啟動時呼叫;與 DU 舊的 align_scene_clock 同語意)。"""
        self.scene_origin = self.tick
        return self.scene_origin

    # ── 迴圈 ────────────────────────────────────────────────
    def _loop(self) -> None:
        from django.db import close_old_connections
        next_t = time.time()
        while not self._stop.is_set():
            t0 = time.perf_counter()
            try:
                self.step_once()
            except Exception as exc:  # noqa: BLE001 — 單拍失敗不能讓時鐘停
                self.step_errors += 1
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.exception("lockstep tick %d failed", self.tick)
            finally:
                close_old_connections()
            self._acc.append((time.perf_counter() - t0) * 1000.0)
            self._measure()
            next_t += self.sim_dt_ms / self.speed_x / 1000.0
            sleep_for = next_t - time.time()
            if sleep_for > 0:
                self._stop.wait(sleep_for)
            else:
                next_t = time.time()   # 跟不上就不補拍,達成倍速會反映在 achieved_speed_x

    def _measure(self) -> None:
        now = time.time()
        w0, t0 = self._win
        if w0 == 0.0:
            self._win = (now, self.tick)
            return
        if now - w0 >= 1.0:
            self.achieved_speed_x = round((self.tick - t0) * self.sim_dt_ms / 1000.0 / (now - w0), 3)
            acc, self._acc = self._acc, []
            if acc:
                self.body_ms = {"avg": round(sum(acc) / len(acc), 2), "max": round(max(acc), 2)}
            self._win = (now, self.tick)

    def _post_step(self, url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        s = self._sessions.get(url)
        if s is None:
            s = self._sessions[url] = requests.Session()
        r = s.post(f"{url}{_STEP_PATH}", json=body, timeout=_STEP_TIMEOUT_SEC)
        r.raise_for_status()
        return (r.json() or {}).get("data") or {}

    def step_once(self) -> dict[str, Any]:
        """跑一拍(測試可直接呼叫)。回傳 {tick, dus_ok, pdus, cqi}。"""
        self.tick += 1
        scene_tick = self.scene_tick
        base = {"tick": self.tick, "scene_tick": scene_tick, "sim_dt_ms": self.sim_dt_ms,
                "speed_x": self.speed_x, "cell_dl_load": self.global_dl_load}
        urls = self.du_urls
        pending, self.pending = self.pending, {}
        bodies = {u: {**base, "indications": pending.get(u, [])} for u in urls}
        if self._pool is not None and len(urls) > 1:
            futs = {u: self._pool.submit(self._post_step, u, bodies[u]) for u in urls}
            results = {}
            for u, f in futs.items():
                try:
                    results[u] = f.result()
                except Exception as exc:  # noqa: BLE001
                    results[u] = exc
        else:
            results = {}
            for u in urls:
                try:
                    results[u] = self._post_step(u, bodies[u])
                except Exception as exc:  # noqa: BLE001
                    results[u] = exc
        parts, owner = [], {}
        for u, res in results.items():
            if isinstance(res, Exception):
                self.step_errors += 1
                self.last_error = f"{u}: {res}"
                if self.step_errors % 50 == 1:
                    logger.warning("DU step failed (%s),累計 %d 次", self.last_error, self.step_errors)
                continue
            dl = res.get("dl_tti")
            if dl:
                parts.append(dl)
                for p in dl.get("pdus") or []:
                    owner[p.get("ue_id")] = u
        merged = merge_dl_tti(parts, scene_tick * self.sim_dt_ms)
        if merged is None:
            return {"tick": self.tick, "dus_ok": len(parts), "pdus": 0, "cqi": 0}
        self.global_dl_load = dict(merged["cell_dl_load"])
        from ran_sim_protocol.fapi import DlTtiRequest
        from ran_sim_protocol.serde import from_dict, to_dict
        from main.apps.fapi_south.services.optional import dl_tti_pipeline
        cqi_list = dl_tti_pipeline.run(from_dict(DlTtiRequest, merged))
        nxt: dict[str, list[dict[str, Any]]] = {}
        for c in cqi_list:
            u = owner.get(c.ue_id)
            if u:
                nxt.setdefault(u, []).append(to_dict(c))
        self.pending = nxt
        return {"tick": self.tick, "dus_ok": len(parts), "pdus": len(merged["pdus"]), "cqi": len(cqi_list)}


_clock: LockstepClock | None = None
_clock_guard = threading.Lock()


def get_clock() -> LockstepClock:
    global _clock
    with _clock_guard:
        if _clock is None:
            _clock = LockstepClock()
        return _clock
