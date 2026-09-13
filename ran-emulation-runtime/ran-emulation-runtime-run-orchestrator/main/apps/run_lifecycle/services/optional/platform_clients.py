
"""跨系統 HTTP client:registry(場景樹、run 狀態)與 UE driver(起/停)。跨 repo 只傳 uuid(backend_rule §12-2)。"""
from __future__ import annotations

import json
import urllib.request

from django.conf import settings


def _post(base: str, path: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(f"{base}{path}", data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _registry(path: str, body: dict, timeout: float = 30.0) -> dict:
    return _post(f"http://{settings.HTTP_REGISTRY_HOST}:{settings.HTTP_REGISTRY_PORT}/api/v0.1/Network_element_registry/", path, body, timeout)


def _ue(path: str, body: dict, timeout: float = 180.0, host: str | None = None) -> dict:
    return _post(f"http://{host or settings.HTTP_UE_DRIVER_HOST}:{settings.HTTP_UE_DRIVER_PORT if host is None else 8000}/api/v0.1/UE/Sim/", path, body, timeout)


def now_iso() -> str:
    from main.apps.run_lifecycle.services.common.timestamp_service import TimestampService
    return TimestampService.get_current_timestamp().isoformat()


def read_full_tree(scene_run_uuid: str) -> dict:
    return _registry("Scene_layout/SceneReader/read_full_tree", {"scene_run_uuid": scene_run_uuid})


def update_scene_run(scene_run_uuid: str, **fields) -> dict:
    return _registry("Simulation_run/SceneRunController/update", {"scene_run_uuid": scene_run_uuid, **fields})


def ue_start(scene_run_uuid: str, speed_x: float, sim_dt_ms: int, host: str | None = None) -> dict:
    return _ue("SimController/start", {"source": "scenario", "scene_run_uuid": scene_run_uuid, "speed_x": speed_x, "sim_dt_ms": sim_dt_ms}, host=host)


def ue_stop(host: str | None = None) -> dict:
    return _ue("SimController/stop", {}, host=host)


# run_instance(registry Simulation_run):每個 per-run 容器一列
def create_run_instance(scene_run_uuid: str, role: str, container_id: str, host_port: int, status: str = "starting") -> dict:
    return _registry("Simulation_run/RunInstanceController/create", {"f_scene_run_uuid": scene_run_uuid, "role": role, "container_id": container_id, "host_port": host_port, "status": status})


def update_run_instance(run_instance_uuid: str, **fields) -> dict:
    return _registry("Simulation_run/RunInstanceController/update", {"run_instance_uuid": run_instance_uuid, **fields})


def list_run_instances(scene_run_uuid: str) -> list[dict]:
    return _registry("Simulation_run/RunInstanceReader/read", {"f_scene_run_uuid": scene_run_uuid}).get("data") or []


def delete_run_instance(run_instance_uuid: str) -> dict:
    return _registry("Simulation_run/RunInstanceController/delete", {"run_instance_uuid": run_instance_uuid})
