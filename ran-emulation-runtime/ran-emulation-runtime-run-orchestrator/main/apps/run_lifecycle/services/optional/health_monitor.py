"""健康輪詢(P4-1):每 run 一條 thread,每 PER_RUN_HEALTH_SEC 秒看容器狀態 + HTTP 存活,寫 registry run_instance.status / last_heartbeat。"""
from __future__ import annotations

import threading
import time
import urllib.request

from django.conf import settings

from main.apps.run_lifecycle.services.optional import container_spawner, platform_clients
from main.utils.logger import get_logger

logger = get_logger(__name__)
_threads: dict[str, "HealthMonitor"] = {}
_lock = threading.Lock()


class HealthMonitor(threading.Thread):
    def __init__(self, scene_run_uuid: str, instances: dict[str, dict]) -> None:
        super().__init__(name=f"health-{scene_run_uuid[-8:]}", daemon=True)
        self.run_uuid = scene_run_uuid; self.instances = instances; self._stop_evt = threading.Event()

    def stop(self) -> None:
        self._stop_evt.set()

    def run(self) -> None:
        names = container_spawner.names_for(self.run_uuid)
        while not self._stop_evt.is_set():
            try:
                st = container_spawner.container_status(self.run_uuid)
                for role, inst in self.instances.items():
                    alive = False
                    if st.get(role) == "running":
                        try:
                            req = urllib.request.Request(container_spawner.health_url(role, names[role], inst.get("host_port")), data=b"{}", headers={"content-type": "application/json"})
                            with urllib.request.urlopen(req, timeout=3) as resp:
                                alive = resp.status < 500
                        except Exception:  # noqa: BLE001
                            alive = False
                    status = "running" if alive else ("starting" if st.get(role) == "running" else st.get(role, "absent"))
                    platform_clients.update_run_instance(inst["run_instance_uuid"], status=status, **({"last_heartbeat": platform_clients.now_iso()} if alive else {}))
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
