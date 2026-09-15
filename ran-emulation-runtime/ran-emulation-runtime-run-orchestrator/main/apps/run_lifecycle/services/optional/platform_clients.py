
"""跨系統 HTTP client:registry(場景樹、run 狀態)與 UE driver(起/停)。跨 repo 只傳 uuid(backend_rule §12-2)。"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from django.conf import settings


def _post(base: str, path: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(f"{base}{path}", data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _registry(path: str, body: dict, timeout: float = 30.0) -> dict:
    return _post(f"http://{settings.HTTP_REGISTRY_HOST}:{settings.HTTP_REGISTRY_PORT}/api/v0.1/Scene_management_backend/", path, body, timeout)


def _ue(path: str, body: dict, timeout: float = 180.0, host: str | None = None) -> dict:
    return _post(f"http://{host or settings.HTTP_UE_DRIVER_HOST}:{settings.HTTP_UE_DRIVER_PORT if host is None else 8000}/api/v0.1/UE/Sim/", path, body, timeout)


def now_iso() -> str:
    from main.apps.run_lifecycle.services.common.timestamp_service import TimestampService
    return TimestampService.get_current_timestamp().isoformat()


def read_full_tree(scene_run_uuid: str) -> dict:
    return _registry("Field_scene/SceneReader/read_full_tree", {"scene_run_uuid": scene_run_uuid})


def update_scene_run(scene_run_uuid: str, **fields) -> dict:
    return _registry("Simulation_run/SceneRunController/update", {"scene_run_uuid": scene_run_uuid, **fields})


def ue_start(scene_run_uuid: str, speed_x: float, sim_dt_ms: int, host: str | None = None) -> dict:
    return _ue("SimController/start", {"source": "scenario", "scene_run_uuid": scene_run_uuid, "speed_x": speed_x, "sim_dt_ms": sim_dt_ms}, host=host)


def ue_stop(host: str | None = None) -> dict:
    # stop 路徑不能等 180 s:CU 卡死時 UE driver 的 release_all 會一直等,撞到 gunicorn worker 上限被 SIGKILL(2026-09-15 06:30 事故)。
    # 45 s 等不到就當 UE driver 已死,照樣往下拆容器。
    return _ue("SimController/stop", {}, timeout=45.0, host=host)


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
    return list_runs_by_status("running")


def list_runs_by_status(status: str) -> list[dict]:
    return _registry("Simulation_run/SceneRunReader/read", {"status": status}).get("data") or []


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


# ── RIC 場景閘道(ric-scenario-gw)──────────────────────────────────
# 模型(RIC 端 2026-09-14):一 scene_run 一 pod,pod 訂閱該 run 的全部 meid;meid → scenario 必須 N:1。
# 我方一個 run 只有一個 CU = 一個 meid,所以 nodes[] 永遠一筆(nodeId 固定 "cu")。
def _gw(path: str, body: dict | None, method: str = "POST", timeout: float = 15.0) -> dict | None:
    from main.utils.logger import get_logger
    log = get_logger(__name__)
    if not settings.RIC_GATEWAY_URL:
        log.info("RIC gateway not configured; would %s %s %s", method, path, body)
        return None
    req = urllib.request.Request(f"{settings.RIC_GATEWAY_URL.rstrip('/')}{path}", data=(json.dumps(body).encode() if body is not None else None),
                                 headers={"content-type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {"status": resp.status}
    except urllib.error.HTTPError as exc:
        body_txt = exc.read().decode("utf-8", "replace")[:300]
        log.warning("RIC gateway %s %s → HTTP %s %s", method, path, exc.code, body_txt)
        return {"error": exc.code, "body": body_txt}
    except Exception as exc:  # noqa: BLE001
        log.warning("RIC gateway %s %s failed: %s", method, path, exc)
        return {"error": str(exc)}


def _plmn_tbcd(mcc: str = "208", mnc: str = "95") -> str:
    return f"{mcc[1]}{mcc[0]}{'F' if len(mnc) == 2 else mnc[2]}{mcc[2]}{mnc[1]}{mnc[0]}".upper()


def ric_register_scenario(scene_run_uuid: str, scene_name: str, meid: str, ran_functions: list[int] | None = None, profile: str | None = None, gnb_id_hex: str = "") -> dict | None:
    """POST /v1/scenarios —— 場景 start 時宣告(E2 Setup 完成前先宣告也可,閘道現查連線狀態)。409 meid-already-bound 表示上次沒清乾淨。
    node 帶 plmnId / nbIdBits:DELETE 時清 R-NIB 第二把 key(GNB:<plmn>:<bits>)要用,key 裡沒有 ranName 字串。"""
    node = {"nodeId": "cu", "meid": meid, "plmnId": _plmn_tbcd(), "nbIdBits": (format(int(gnb_id_hex, 16), "022b") if gnb_id_hex else None)}
    body = {"scenarioId": scene_run_uuid, "labels": {"scene_name": scene_name}, "profile": profile or settings.RIC_GATEWAY_PROFILE,
            "nodes": [node], "ranFunctions": ran_functions or [2, 3, 4, 5, 6],
            "controlPolicy": {"allowedStyles": ["rc-reportcgi", "anr-add"], "allowWrite": True}}
    gw = _gw("/v1/scenarios", body)
    # 2026-09-16:409 meid-already-bound = 閘道還留著上一輪(通常是 DELETE 逾時)綁這個 meid 的舊場景 → 找出來 DELETE 再登記一次
    if isinstance(gw, dict) and gw.get("error") == 409 and "meid-already-bound" in str(gw.get("body", "")):
        stale = [sc.get("scenarioId") for sc in (_gw("/v1/scenarios", None, method="GET", timeout=20.0) or [])
                 if isinstance(sc, dict) and any((n or {}).get("meid") == meid for n in (sc.get("nodes") or {}).values())]
        for sid in stale:
            logger.warning("RIC gateway meid %s 被舊場景 %s 佔住 → DELETE 後重試登記", meid, sid)
            _gw(f"/v1/scenarios/{sid}", None, method="DELETE", timeout=30.0)
        if stale:
            gw = _gw("/v1/scenarios", body)
    return gw


def ric_unregister_scenario(scene_run_uuid: str) -> dict | None:
    """DELETE /v1/scenarios/{id}(RIC 端尚未說明是否存在;404/405 只記 log)。"""
    return _gw(f"/v1/scenarios/{scene_run_uuid}", None, method="DELETE")


def ric_rnib_clear(ran_name: str, gnb_id_hex: str, plmn_mcc: str = "208", plmn_mnc: str = "95", force: bool = False) -> dict | None:
    """POST /v1/rnib/clear —— stop 後(SCTP 已關)清 RAN:<name> / GNB:<plmn>:<bits> / GNB set 成員。RAN 還連著預設拒絕(要 force)。"""
    mnc = plmn_mnc.zfill(3) if len(plmn_mnc) == 2 else plmn_mnc
    # PLMN TBCD:MCC 208 MNC 95 → 02F859(MNC 2 位補 F)
    m = plmn_mcc; n = plmn_mnc
    plmn_hex = f"{m[1]}{m[0]}{'F' if len(n) == 2 else n[2]}{m[2]}{n[1]}{n[0]}".upper()
    body = {"ran_name": ran_name, "plmn": plmn_hex, "gnb_id_bits": format(int(gnb_id_hex, 16), "022b") if gnb_id_hex else ""}
    if force:
        body["force"] = True
    return _gw("/v1/rnib/clear", body)


def ric_node_view(meid: str) -> dict | None:
    """GET /v1/nodes/{meid} → 哪個 pod 在看這個 meid(監控頁用)。"""
    return _gw(f"/v1/nodes/{meid}", None, method="GET", timeout=20.0)   # 閘道單筆 GET 實測固定 ~5 s(2026-09-16)


def ric_deploy_xapp(scene_run_uuid: str, image: str | None = None, env: dict | None = None) -> dict | None:
    """POST /v1/scenarios/{id}/xapp —— 為這個場景部署專屬 xApp pod(profile 預設映像;場景 DELETE 會一併拆)。
    pod 會被注入 SCENARIO_ID / SCENARIO_MEIDS(只含本場景)/ CONTROL_GATEWAY。"""
    body: dict = {}
    if image:
        body["image"] = image
    if env:
        body["env"] = env
    return _gw(f"/v1/scenarios/{scene_run_uuid}/xapp", body, timeout=60.0)


def ric_scenario_view(scene_run_uuid: str) -> dict | None:
    """GET /v1/scenarios/{id} → 場景主檔 + 每 node 即時 e2ConnectionStatus / subscriptionCount / xappName。"""
    return _gw(f"/v1/scenarios/{scene_run_uuid}", None, method="GET", timeout=20.0)   # 同上
