
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


def _ue(path: str, body: dict, timeout: float = 180.0) -> dict:
    return _post(f"http://{settings.HTTP_UE_DRIVER_HOST}:{settings.HTTP_UE_DRIVER_PORT}/api/v0.1/UE/Sim/", path, body, timeout)


def read_full_tree(scene_run_uuid: str) -> dict:
    return _registry("Scene_layout/SceneReader/read_full_tree", {"scene_run_uuid": scene_run_uuid})


def update_scene_run(scene_run_uuid: str, **fields) -> dict:
    return _registry("Simulation_run/SceneRunController/update", {"scene_run_uuid": scene_run_uuid, **fields})


def ue_start(scene_run_uuid: str, speed_x: float, sim_dt_ms: int) -> dict:
    return _ue("SimController/start", {"source": "scenario", "scene_run_uuid": scene_run_uuid, "speed_x": speed_x, "sim_dt_ms": sim_dt_ms})


def ue_stop() -> dict:
    return _ue("SimController/stop", {})
