
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


def read_scene_tree(scene_uuid: str) -> dict:
    """依場景(而非 run)讀完整樹 —— Agent 介面 I-2 在觸發模擬前就要拿配置。"""
    return _registry("Field_scene/SceneReader/read_full_tree", {"scene_uuid": scene_uuid})


def read_scene_run(scene_run_uuid: str) -> dict:
    return _registry("Simulation_run/SceneRunReader/read", {"scene_run_uuid": scene_run_uuid})


def read_scene_tree_by_run(scene_run_uuid: str) -> dict:
    return _registry("Field_scene/SceneReader/read_full_tree", {"scene_run_uuid": scene_run_uuid})


def list_scenes() -> dict:
    return _registry("Field_scene/SceneReader/read", {})


def list_scene_runs() -> dict:
    return _registry("Simulation_run/SceneRunReader/read", {})


def read_run_knobs(scene_run_uuid: str) -> list[dict]:
    """該 run 的旋鈕列(原始列,含 run_knob_uuid)。"""
    return _registry("Simulation_run/RunKnobReader/read", {"f_scene_run_uuid": scene_run_uuid}).get("data") or []


def set_run_knob(scene_run_uuid: str, key: str, value) -> dict:
    """寫一個 run knob:同 scene_run + key 已存在就 update,否則 create。

    2026-09-22 修正:RunKnobController/create 是**純新增**,不是 upsert(先前寫錯,
    每觸發一次 I-3 就多一列 run_seed,實測堆了 17 列重複)。而全樹把 knobs 壓成
    dict 時是無序 filter 的最後一筆贏 —— 重複列會讓「這次到底用哪個 seed」變成
    看資料庫排序,決定性就沒了。
    """
    hit = next((r for r in read_run_knobs(scene_run_uuid) if r.get("key") == key), None)
    if hit and hit.get("run_knob_uuid"):
        return _registry("Simulation_run/RunKnobController/update",
                         {"run_knob_uuid": hit["run_knob_uuid"], "value": value})
    return _registry("Simulation_run/RunKnobController/create",
                     {"f_scene_run_uuid": scene_run_uuid, "key": key, "value": value})


def scene_bounds(scene_uuid: str) -> dict:
    return _registry("Field_scene/SceneGeometryReader/bounds", {"scene_uuid": scene_uuid})


def update_scene_run(scene_run_uuid: str, **fields) -> dict:
    return _registry("Simulation_run/SceneRunController/update", {"scene_run_uuid": scene_run_uuid, **fields})


def ue_start(scene_run_uuid: str, speed_x: float, sim_dt_ms: int, host: str | None = None,
             ue_limit: int | None = None, ue_seed: int = 0) -> dict:
    body = {"source": "scenario", "scene_run_uuid": scene_run_uuid,
            "speed_x": speed_x, "sim_dt_ms": sim_dt_ms}
    # 2026-09-22:外部 Agent 的 I-3 ue_count(只能往下裁)。不給就完全照舊。
    if ue_limit:
        body["ue_limit"] = int(ue_limit)
        body["ue_seed"] = int(ue_seed)
    return _ue("SimController/start", body, host=host)


def ue_stop(host: str | None = None) -> dict:
    # stop 路徑不能等 180 s:CU 卡死時 UE driver 的 release_all 會一直等,撞到 gunicorn worker 上限被 SIGKILL(2026-09-15 06:30 事故)。
    # 45 s 等不到就當 UE driver 已死,照樣往下拆容器。
    return _ue("SimController/stop", {}, timeout=45.0, host=host)


# run_instance(registry Simulation_run):每個 per-run 容器一列
def create_run_instance(scene_run_uuid: str, role: str, container_id: str, host_port: int, status: str = "starting",
                        **extra) -> dict:
    """extra:多 gNB 的實例資訊 —— name(容器名)、f_gnb_uuid、f_du_uuid、e2_node_id(registry P1 新欄位)。"""
    return _registry("Simulation_run/RunInstanceController/create", {"f_scene_run_uuid": scene_run_uuid, "role": role, "container_id": container_id, "host_port": host_port, "status": status,
                                                                     **{k: v for k, v in extra.items() if v not in (None, "")}})


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


from main.utils.logger import get_logger as _get_logger  # noqa: E402

logger = _get_logger(__name__)   # 2026-09-17:下面的 meid 佔用重試原本引用未定義的 logger(NameError)


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


def ric_register_scenario(scene_run_uuid: str, scene_name: str, meid: str, ran_functions: list[int] | None = None, profile: str | None = None, gnb_id_hex: str = "", purpose: str = "") -> dict | None:
    """POST /v1/scenarios —— 場景 start 時宣告(E2 Setup 完成前先宣告也可,閘道現查連線狀態)。409 meid-already-bound 表示上次沒清乾淨。
    node 帶 plmnId / nbIdBits:DELETE 時清 R-NIB 第二把 key(GNB:<plmn>:<bits>)要用,key 裡沒有 ranName 字串。"""
    node = {"nodeId": "cu", "meid": meid, "plmnId": _plmn_tbcd(), "nbIdBits": (format(int(gnb_id_hex, 16), "022b") if gnb_id_hex else None)}
    # labels.purpose="validation" → RIC 端才會在 T0+10 分鐘送主動探測(唯讀 ReportCGI);
    # 沒帶就只做唯讀觀測,不會有任何東西送到我們的 gNB(RIC 端 2026-09-19 17:19 起生效)
    labels = {"scene_name": scene_name}
    if purpose:
        labels["purpose"] = purpose
    body = {"scenarioId": scene_run_uuid, "labels": labels, "profile": profile or settings.RIC_GATEWAY_PROFILE,
            "nodes": [node], "ranFunctions": ran_functions or [2, 3, 4, 5, 6],
            "controlPolicy": {"allowedStyles": list(getattr(settings, "RIC_GATEWAY_ALLOWED_STYLES", None) or ["rc-reportcgi", "anr-add"]),
                              "allowWrite": True},
            # 2026-09-16 RIC 端新增:開場時自動清掉同 meid 的殘留 E2 關聯(拆臨時節點後 m-release 無 Removal 留下的)。
            # 只清「沒有 xApp 在收」的節點;常駐 e00 會被閘道擋下(409 ran-live)。
            "cleanStale": True}
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


def ric_register_scenario_nodes(scene_run_uuid: str, scene_name: str, nodes: list[dict], ran_functions: list[int] | None = None,
                                profile: str | None = None, purpose: str = "") -> dict | None:
    """多 gNB(計畫 D4):一場宣告 N 個 node,每個 gNB 一筆
    {nodeId: registry gNB 名稱, meid, plmnId, nbIdBits}。必須在任何 e2adapter 做 E2 Setup 之前呼叫 ——
    否則 RIC 常駐 xApp 會先接手還沒綁定的 meid。409 meid-already-bound 的處理與單 node 相同(逐 meid)。"""
    labels = {"scene_name": scene_name}
    if purpose:
        labels["purpose"] = purpose
    body = {"scenarioId": scene_run_uuid, "labels": labels, "profile": profile or settings.RIC_GATEWAY_PROFILE,
            "nodes": nodes, "ranFunctions": ran_functions or [2, 3, 4, 5, 6],
            "controlPolicy": {"allowedStyles": list(getattr(settings, "RIC_GATEWAY_ALLOWED_STYLES", None) or ["rc-reportcgi", "anr-add"]),
                              "allowWrite": True},
            "cleanStale": True}
    gw = _gw("/v1/scenarios", body)
    if isinstance(gw, dict) and gw.get("error") == 409 and "meid-already-bound" in str(gw.get("body", "")):
        meids = {n.get("meid") for n in nodes}
        stale = [sc.get("scenarioId") for sc in (_gw("/v1/scenarios", None, method="GET", timeout=20.0) or [])
                 if isinstance(sc, dict) and sc.get("scenarioId") != scene_run_uuid
                 and any((n or {}).get("meid") in meids for n in (sc.get("nodes") or {}).values())]
        for sid in stale:
            logger.warning("RIC gateway meid 被舊場景 %s 佔住 → DELETE 後重試登記", sid)
            _gw(f"/v1/scenarios/{sid}", None, method="DELETE", timeout=30.0)
        if stale:
            gw = _gw("/v1/scenarios", body)
    return gw


def ric_register_nodes_with_retry(*args, attempts: int = 8, every_sec: float = 5.0, **kwargs) -> dict | None:
    import time as _t
    gw = None
    for i in range(max(1, attempts)):
        gw = ric_register_scenario_nodes(*args, **kwargs)
        if gw and not (isinstance(gw, dict) and gw.get("error")):
            return gw
        if i + 1 < attempts:
            logger.warning("RIC gateway 宣告失敗(%d/%d):%s —— %.0fs 後重試", i + 1, attempts,
                           (gw or {}).get("error") if isinstance(gw, dict) else gw, every_sec)
            _t.sleep(every_sec)
    return gw


def ric_gateway_alive(timeout: float = 5.0) -> bool:
    """RIC 場景閘道現在問得到嗎。I-3 觸發前先探:閘道換版的空窗裡起的場次會變成
    scenario=none(2026-09-22 12:28 實際發生),資料對 Agent 沒有用,不如直接拒絕。"""
    r = _gw("/v1/scenarios", None, method="GET", timeout=timeout)
    return r is not None and not (isinstance(r, dict) and r.get("error"))


def ric_register_scenario_with_retry(*args, attempts: int = 8, every_sec: float = 5.0, **kwargs) -> dict | None:
    """宣告失敗就重試,覆蓋閘道 Recreate 的空窗(約 20 秒)。最後一次的結果原樣回傳。"""
    import time as _t
    gw = None
    for i in range(max(1, attempts)):
        gw = ric_register_scenario(*args, **kwargs)
        if gw and not (isinstance(gw, dict) and gw.get("error")):
            return gw
        if i + 1 < attempts:
            logger.warning("RIC gateway 宣告失敗(%d/%d):%s —— %.0fs 後重試", i + 1, attempts,
                           (gw or {}).get("error") if isinstance(gw, dict) else gw, every_sec)
            _t.sleep(every_sec)
    return gw


def ric_activate_scenario(scene_run_uuid: str) -> dict | None:
    """POST /v1/scenarios/{id}/activate(閘道 0.8.4):場景啟用後才能經閘道下控制。
    閘道會現查每顆 gNB 是否 CONNECTED,沒連上回 409 並指出哪一顆;回應帶 nodes.<id>.gen 與 warnings(沒訂閱的 gNB)。"""
    return _gw(f"/v1/scenarios/{scene_run_uuid}/activate", {}, timeout=30.0)


def ric_deactivate_scenario(scene_run_uuid: str) -> dict | None:
    """POST /v1/scenarios/{id}/deactivate —— 重佈場景 / 換劇本前呼叫(刪場景則不必)。"""
    return _gw(f"/v1/scenarios/{scene_run_uuid}/deactivate", {}, timeout=30.0)


def _dt_nodes_subscribed(scene_run_uuid: str) -> bool:
    """這場每個 gNB 的 CU 都已有至少一筆 active E2 訂閱(= RIC 的訂閱真的到了 RAN)。查不到拓樸就不擋。"""
    from main.apps.run_lifecycle.services.optional import container_spawner
    try:
        topo = container_spawner.topology_of(scene_run_uuid)
    except Exception:  # noqa: BLE001
        topo = None
    if topo is None or not topo.gnbs:
        return True
    for g in topo.gnbs:
        try:
            req = urllib.request.Request(f"{g.cu_url}/api/v0.1/CU/E2/Subscription/list", data=b"{}",
                                         headers={"content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as r:
                body = json.loads(r.read().decode() or "{}")
            if int((body.get("data") or {}).get("count") or 0) < 1:
                return False
        except Exception:  # noqa: BLE001
            return False
    return True


def ric_activate_when_ready(scene_run_uuid: str, timeout_sec: float = 180.0, every_sec: float = 5.0) -> dict | None:
    """等 CU 的 E2 Setup 完成再啟用:409(gNB 還沒 CONNECTED)就每 every_sec 秒重試,直到成功或逾時。"""
    import time as _time
    deadline = _time.time() + timeout_sec
    res = None
    # 計畫 D4:全部 node CONNECTED **且每個 meid 都已有 xApp 訂閱**才 activate —— 只看 CONNECTED 的話,
    # 最後一個 node 剛連上、xApp 還沒來得及訂閱,activate 會帶 "has no E2 subscription" 警告(2026-09-27 run 4 實測)。
    # 2026-09-28:閘道的 subscriptionCount 含 RIC 常駐 mobiflow 對每個 meid 的訂閱,幾乎一連上就 > 0,
    # 擋不住「場景 xApp 的訂閱還沒真的到 RAN」(容量測試 cap_03:e81/e82 的訂閱晚 75 s)。另外要求 DT 端
    # 每個 CU 都已收到 KPM 訂閱(三種訂閱中最後到的那筆,存在 CU 的訂閱表)。
    # 最多等到逾時前 20 s;等不到仍照舊 activate(警告照樣記),不讓場景卡在 declared。
    sub_deadline = _time.time() + max(timeout_sec - 20.0, timeout_sec / 2)
    while _time.time() < sub_deadline:
        view = ric_scenario_view(scene_run_uuid)
        nodes = (view or {}).get("nodes") if isinstance(view, dict) else None
        if isinstance(nodes, dict) and nodes and all(
                str((n or {}).get("e2ConnectionStatus") or "").upper() == "CONNECTED"
                and int((n or {}).get("subscriptionCount") or 0) > 0 for n in nodes.values()) \
                and _dt_nodes_subscribed(scene_run_uuid):
            break
        _time.sleep(every_sec)
    else:
        logger.warning("RIC gateway activate %s:等訂閱逾時,照舊 activate", scene_run_uuid)
    while _time.time() < deadline:
        res = ric_activate_scenario(scene_run_uuid)
        if isinstance(res, dict) and not res.get("error"):
            if res.get("warnings"):
                logger.warning("RIC gateway activate %s warnings: %s", scene_run_uuid, res.get("warnings"))
            logger.info("RIC gateway activate %s → gen %s", scene_run_uuid,
                        {k: (v or {}).get("gen") for k, v in (res.get("nodes") or {}).items()})
            return res
        if not (isinstance(res, dict) and res.get("error") == 409):
            break   # 409 以外(閘道沒這個端點、網路錯)不再等
        _time.sleep(every_sec)
    logger.warning("RIC gateway activate %s 未成功: %s", scene_run_uuid, res)
    return res


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
