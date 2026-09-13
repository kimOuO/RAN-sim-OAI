
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


def list_running_runs() -> list[dict]:
    return _registry("Simulation_run/SceneRunReader/read", {"status": "running"}).get("data") or []


def notify_ric_stopped(scene_run_uuid: str, e2_node_id: str, gnb_id_hex: str, plmn_mcc: str = "208", plmn_mnc: str = "95") -> dict | None:
    """收尾第 4 步:通知 RIC 端這個 E2 node 已收掉,請清 R-NIB(RAN:<ranName> 與 GNB:<plmn>:<gnb-id bits> 兩把)。
    RIC_STOP_WEBHOOK_URL 沒設就只記 log(由人工跑 rnib_clear_gnb.sh)。"""
    from main.utils.logger import get_logger
    log = get_logger(__name__)
    gnb_bits = format(int(gnb_id_hex, 16), "022b") if gnb_id_hex else ""
    payload = {"event": "scene_run_stopped", "scene_run_uuid": scene_run_uuid, "ran_name": e2_node_id, "gnb_id_hex": gnb_id_hex,
               "gnb_id_bits": gnb_bits, "plmn_mcc": plmn_mcc, "plmn_mnc": plmn_mnc, "stopped_at": now_iso()}
    log.info("RIC R-NIB cleanup needed: %s", payload)
    if not settings.RIC_STOP_WEBHOOK_URL:
        return None
    try:
        return _post(settings.RIC_STOP_WEBHOOK_URL, "", payload, 10.0)
    except Exception as exc:  # noqa: BLE001
        log.warning("RIC stop webhook failed: %s", exc)
        return {"error": str(exc)}
