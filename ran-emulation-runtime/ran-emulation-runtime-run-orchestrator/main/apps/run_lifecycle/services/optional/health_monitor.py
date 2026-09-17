"""健康輪詢(P4-1):每 run 一條 thread,每 PER_RUN_HEALTH_SEC 秒看容器狀態 + HTTP 存活,寫 registry run_instance.status / last_heartbeat。"""
from __future__ import annotations

import json
import threading
import time
import urllib.request

from django.conf import settings

from main.apps.run_lifecycle.services.optional import container_spawner, platform_clients
from main.utils.logger import get_logger

logger = get_logger(__name__)
_threads: dict[str, "HealthMonitor"] = {}
_lock = threading.Lock()
# 2026-09-17:自動重啟紀錄放在模組層。以前放在 HealthMonitor 實例上,但重啟流程會建新的監控執行緒,
# 冷卻時間跟著歸零 → e03 陷入重啟迴圈(閘道世代號衝到 129)。
_restart_history: dict[str, list[float]] = {}
MAX_AUTO_RESTARTS_PER_HOUR = 3


# 外部依賴(RIC)的問題:照樣標 degraded 讓監控頁看得到,但**不觸發自動重啟** ——
# 重啟整個 run 修不好 RIC 那邊,只會打斷模擬(2026-09-16:RIC SCTP 斷線時每 10 分鐘被重啟一次)。
EXTERNAL_ISSUE_PREFIXES = ("SCTP 未連線",)


def is_external(detail: str) -> bool:
    return bool(detail) and detail.startswith(EXTERNAL_ISSUE_PREFIXES)


# 記憶體(2026-09-16 事故後):容器用量逼近 mem_limit 就標 degraded,持續下去走既有的自動重啟,
# 在 OOM killer 動手前正常收尾重來;主機可用記憶體太低只記 log(元兇可能是別的服務,重啟 run 沒用)。
MEM_CHECK_SEC = 60.0
MEM_WARN_RATIO = 0.85
HOST_MEM_WARN_RATIO = 0.10


def memory_issue(name: str) -> str:
    try:
        import docker
        s = docker.from_env().containers.get(name).stats(stream=False).get("memory_stats") or {}
        usage = float(s.get("usage") or 0) - float((s.get("stats") or {}).get("inactive_file") or 0)
        limit = float(s.get("limit") or 0)
    except Exception:  # noqa: BLE001
        return ""
    if limit <= 0 or limit >= 1 << 50 or usage / limit < MEM_WARN_RATIO:
        return ""
    return f"記憶體 {usage / 2**20:.0f}/{limit / 2**20:.0f} MiB({100 * usage / limit:.0f}%)逼近上限"


def host_memory_low() -> str:
    try:
        info = {l.split(":")[0]: float(l.split()[1]) for l in open("/proc/meminfo")}
        avail, total = info["MemAvailable"], info["MemTotal"]
    except Exception:  # noqa: BLE001
        return ""
    return f"主機可用記憶體 {avail / 2**20:.1f}/{total / 2**20:.1f} GiB" if avail / total < HOST_MEM_WARN_RATIO else ""


def dependency_issue(role: str, data: dict) -> str:
    """看各角色 status 回應裡的依賴鏈欄位;回傳問題描述,正常回空字串。
    2026-09-15 事故:adapter HTTP 活著、SCTP CONNECTED,但打 sim CU 全失敗 → 之前只看「活著」完全看不出來。"""
    try:
        if role == "e2adapter":
            sctp = data.get("sctp_link") or {}; bridge = data.get("sim_bridge") or {}
            if sctp.get("enabled") and not sctp.get("connected"):
                return f"SCTP 未連線 {sctp.get('target_host')}:{sctp.get('target_port')} {sctp.get('last_error') or ''}".strip()
            if bridge.get("last_error"):
                return f"sim CU 不可達 {bridge.get('cu_url')}: {str(bridge['last_error'])[:120]}"
        elif role == "ue":
            failed = data.get("attach_failed") or []; errs = data.get("scene_apply_errors") or []
            if errs:
                return f"scene apply 失敗 {len(errs)} 筆: {str(errs[0])[:100]}"
            if failed:
                return f"UE attach 失敗 {len(failed)} 台: {', '.join(map(str, failed[:5]))}"
        elif role == "du":
            if data.get("last_error"):
                return f"DU: {str(data['last_error'])[:120]}"
            # DU 容器被重啟後 tick 不會自己恢復(2026-09-15 實測:HTTP 活著、F1 Setup 通過、tick_count 0),整場靜止但沒人知道
            if data.get("is_running") is False:
                return "DU tick 未運行(容器重啟後未恢復?)"
    except Exception:  # noqa: BLE001
        return ""
    return ""


def _dump_stacks(name: str) -> None:
    """卡死的容器先留堆疊再重啟:SIGUSR1 → faulthandler(CU 有註冊)寫到容器 stderr。"""
    try:
        import docker
        docker.from_env().containers.get(name).kill(signal="SIGUSR1")
        time.sleep(2)
    except Exception as exc:  # noqa: BLE001
        logger.warning("dump stacks %s failed: %s", name, exc)


def _auto_restart(run_uuid: str, reason: str) -> None:
    """經自家 API stop → start(重用完整收尾/啟動流程:RIC 解除登記、容器重建、UE 重新起場)。"""
    base = f"http://127.0.0.1:8000/api/v0.1/Run_orchestrator/Run_lifecycle/LaunchController"
    body = json.dumps({"scene_run_uuid": run_uuid}).encode()
    for action in ("stop", "start"):
        try:
            req = urllib.request.Request(f"{base}/{action}", data=body, headers={"content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=540) as resp:
                logger.warning("auto-restart %s %s → HTTP %s", run_uuid, action, resp.status)
        except Exception as exc:  # noqa: BLE001
            logger.error("auto-restart %s %s failed: %s", run_uuid, action, exc)
            if action == "stop":
                continue   # stop 失敗(容器已死)照樣 start,spawn 會先移除同名容器
    try:
        platform_clients.update_scene_run(run_uuid, notes=f"auto-restart {platform_clients.now_iso()}: {reason[:200]}")
    except Exception:  # noqa: BLE001
        pass


class HealthMonitor(threading.Thread):
    def __init__(self, scene_run_uuid: str, instances: dict[str, dict]) -> None:
        super().__init__(name=f"health-{scene_run_uuid[-8:]}", daemon=True)
        self.run_uuid = scene_run_uuid; self.instances = instances; self._stop_evt = threading.Event()
        self._unhealthy_since: float | None = None   # 任一角色非 running 的起點
        self._last_restart_at: float = 0.0
        self._last_mem_check: float = 0.0
        self._mem_detail: dict[str, str] = {}   # role → 最近一次記憶體檢查結果(兩次檢查之間沿用)

    def stop(self) -> None:
        self._stop_evt.set()

    def run(self) -> None:
        names = container_spawner.names_for(self.run_uuid)
        while not self._stop_evt.is_set():
            try:
                st = container_spawner.container_status(self.run_uuid)
                if time.time() - self._last_mem_check >= MEM_CHECK_SEC:
                    self._last_mem_check = time.time()
                    self._mem_detail = {r: memory_issue(names[r]) for r in self.instances if st.get(r) == "running"}
                    low = host_memory_low()
                    if low:
                        logger.warning("run %s: %s(不重啟 run,請查主機上其他服務)", self.run_uuid, low)
                unhealthy: list[str] = []
                for role, inst in self.instances.items():
                    alive = False; detail = ""
                    if st.get(role) == "running":
                        try:
                            req = urllib.request.Request(container_spawner.health_url(role, names[role], inst.get("host_port")), data=b"{}", headers={"content-type": "application/json"})
                            with urllib.request.urlopen(req, timeout=3) as resp:
                                alive = resp.status < 500
                                body = json.loads(resp.read().decode() or "{}") if alive else {}
                            detail = dependency_issue(role, (body or {}).get("data") or {}) or self._mem_detail.get(role, "")
                        except Exception:  # noqa: BLE001
                            alive = False
                    else:
                        detail = f"container {st.get(role, 'absent')}"
                    status = ("degraded" if detail else "running") if alive else ("starting" if st.get(role) == "running" else st.get(role, "absent"))
                    platform_clients.update_run_instance(inst["run_instance_uuid"], status=status, health_detail=detail, **({"last_heartbeat": platform_clients.now_iso()} if alive else {}))
                    if status != "running" and not (status == "degraded" and is_external(detail)):
                        unhealthy.append(f"{role}:{status}{(' ' + detail) if detail else ''}")
                # 自動復原(2026-09-15 06:30 CU 卡死 55 分鐘無人處理):連續不健康超過 PER_RUN_AUTO_RESTART_SEC 就重啟整個 run;
                # 剛 spawn 的 starting 期不算(啟動 60 s 內不判);兩次重啟間隔至少 PER_RUN_AUTO_RESTART_COOLDOWN_SEC。
                now = time.time()
                if unhealthy:
                    self._unhealthy_since = self._unhealthy_since or now
                    limit = float(getattr(settings, "PER_RUN_AUTO_RESTART_SEC", 120) or 0)
                    cooldown = float(getattr(settings, "PER_RUN_AUTO_RESTART_COOLDOWN_SEC", 600) or 600)
                    hist = [t for t in _restart_history.get(self.run_uuid, []) if now - t < 3600]
                    _restart_history[self.run_uuid] = hist
                    last = hist[-1] if hist else 0.0
                    if limit > 0 and now - self._unhealthy_since >= limit and len(hist) >= MAX_AUTO_RESTARTS_PER_HOUR:
                        if not getattr(self, "_cap_logged", False):
                            self._cap_logged = True
                            logger.error("run %s 1 小時內已自動重啟 %d 次,停止自動重啟,請人工處理(%s)",
                                         self.run_uuid, len(hist), "; ".join(unhealthy))
                    elif limit > 0 and now - self._unhealthy_since >= limit and now - last >= cooldown:
                        reason = "; ".join(unhealthy)
                        logger.error("run %s unhealthy for %.0fs (%s) → auto-restart", self.run_uuid, now - self._unhealthy_since, reason)
                        self._last_restart_at = now; self._unhealthy_since = None
                        _restart_history.setdefault(self.run_uuid, []).append(now)
                        for role in ("cu", "du"):
                            if any(u.startswith(f"{role}:") for u in unhealthy):
                                _dump_stacks(names[role])
                        threading.Thread(target=_auto_restart, args=(self.run_uuid, reason), name=f"auto-restart-{self.run_uuid[-8:]}", daemon=True).start()
                        return   # 這條監控由 start 重新建立
                else:
                    self._unhealthy_since = None
            except Exception as exc:  # noqa: BLE001
                logger.warning("health poll %s: %s", self.run_uuid, exc)
            self._stop_evt.wait(settings.PER_RUN_HEALTH_SEC)


def start_monitor(scene_run_uuid: str, instances: dict[str, dict]) -> None:
    with _lock:
        old = _threads.get(scene_run_uuid)
        if old and old.is_alive():
            old.stop()
        t = HealthMonitor(scene_run_uuid, instances); _threads[scene_run_uuid] = t; t.start()


def stop_monitor(scene_run_uuid: str) -> None:
    with _lock:
        t = _threads.pop(scene_run_uuid, None)
    if t:
        t.stop(); t.join(5)
