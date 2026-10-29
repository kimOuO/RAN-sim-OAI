"""
O1(SMO)每 run 自動起:每個 gNB 一顆 telnet facade + 兩顆 OAI o1-adapter(CU-CP / DU 身分)。
2026-09-29 D3/D4。設計見 XAPP_DT/o1_smo_plan/01_計畫/O1_對接計畫_v1.1_2026-09-29.md、docs/api/o1_interface.md。

- 容器都掛 `ransim.scene_run_uuid` 標籤 → container_spawner.teardown() 會一併停掉,不需另寫 stop。
- 不進 health_monitor 的 instances(沒有 HTTP 健康端點);只靠 docker 的 restart policy。
- 埠(slot = e2_port - 8400,16..255):
    facade(host network):CU-CP telnet 9000+2·slot、DU telnet 9001+2·slot
    adapter-cucp:NETCONF 1830+2·slot、SFTP 1222+2·slot;ME = meid
    adapter-du  :NETCONF 1831+2·slot、SFTP 1223+2·slot;ME = meid_du<gnb_du_id>
- ME 生命週期通知:寫到 PER_RUN_LOG_DIR/<rid>/o1/notify_<added|removed>.md(由人或腳本轉到 SMO 共用資料夾)。
"""
from __future__ import annotations

import datetime as _dt
import os
import pathlib

import docker
from django.conf import settings

from main.utils.logger import get_logger

logger = get_logger(__name__)

O1_ENABLE = os.environ.get("O1_SMO_ENABLE", "on").lower() in ("1", "on", "true", "yes")
O1_FACADE_IMAGE = os.environ.get("O1_FACADE_IMAGE", "o1-telnet-facade:dt")
O1_ADAPTER_IMAGE = os.environ.get("O1_ADAPTER_IMAGE", "adapter-gnb:dt")
O1_HOST_IP = os.environ.get("O1_HOST_IP", os.environ.get("SCTP_BIND_IP", "10.3.0.217"))
O1_VES_URL = os.environ.get("O1_VES_URL", "http://10.3.0.204:30417/eventListener/v7")
O1_PM_INTERVAL = os.environ.get("O1_PM_INTERVAL", "900")
O1_NETWORK = getattr(settings, "PER_RUN_NETWORK", "ransim-net")

ROLE_FACADE = "o1facade"
ROLE_ADAPTER = "o1adapter"


def _slot(g) -> int:
    return int(g.e2_port) - 8400


DU_PORT_STRIDE = 1024   # 多 DU(2026-10-01):第 k 個 DU 的埠 = 第 0 個 + 1024·k(slot 最大 255 → 2·255+1831+1024·3 < 6000,不與既有服務重疊)


def ports_for(g, k: int = 0) -> dict:
    s = _slot(g)
    return {
        "facade_cucp": 9000 + 2 * s, "facade_du": 9001 + 2 * s + DU_PORT_STRIDE * k,
        "cucp_netconf": 1830 + 2 * s, "cucp_sftp": 1222 + 2 * s,
        "du_netconf": 1831 + 2 * s + DU_PORT_STRIDE * k, "du_sftp": 1223 + 2 * s + DU_PORT_STRIDE * k,
    }


def du_list(g) -> list[dict]:
    """gNB 內每個 DU 一個 O1 ME:[{k, index, gnb_du_id, me, cells:[local_cell_id...]}];沒有 DU 時給一個預設。"""
    out = []
    for k, d in enumerate(g.dus or []):
        out.append({"k": k, "index": d.index, "gnb_du_id": int(d.gnb_du_id), "me": f"{g.meid}_du{int(d.gnb_du_id)}",
                    "cells": [int(c.local_cell_id) for c in (d.cells or [])] or [0]})
    return out or [{"k": 0, "index": None, "gnb_du_id": 1, "me": f"{g.meid}_du1", "cells": [0]}]


def me_names(g) -> dict:
    """相容舊呼叫:cucp / du(第一個 DU)/ gnb_du_id;新增 dus(全部)。"""
    dus = du_list(g)
    return {"cucp": g.meid, "du": dus[0]["me"], "gnb_du_id": dus[0]["gnb_du_id"], "dus": dus}


def _overrides() -> dict:
    """驗證用的暫時覆寫(2026-10-01):PER_RUN_LOG_DIR/_o1_overrides.json,例 {"pm_interval": 60}。
    不用重啟編排服務、不動其他 run 的預設;檔案不存在就沒有覆寫。A1 閉環的驗證 run 要 60 秒 PM 週期時用。"""
    import json as _json
    p = pathlib.Path(getattr(settings, "PER_RUN_LOG_DIR", "/data/run_logs")) / "_o1_overrides.json"
    try:
        return _json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("O1 overrides unreadable: %s", exc)
        return {}


def plan(rid: str, topo, instances: dict, scenario_id: str = "") -> list[dict]:
    """依 run 的 topo 與已起的 CU/DU host port,列出要起的 O1 容器。"""
    ov = _overrides()
    pm_interval = str(int(ov.get("pm_interval") or O1_PM_INTERVAL))
    if pm_interval != str(O1_PM_INTERVAL):
        logger.info("O1 override: pm_interval=%s (default %s)", pm_interval, O1_PM_INTERVAL)
    # runId 每次執行唯一(SMO 2026-09-30 選 A):rid 跟著場景,同場景重啟會相同 → 加啟動時間。
    run_tag = f"{rid}-{_dt.datetime.now(_dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    items: list[dict] = []
    for g in topo.gnbs:
        cu = instances.get(f"cu-{g.e2_index}") or {}
        cu_port = cu.get("host_port")
        dus = []
        for d in du_list(g):
            inst = (instances.get(f"du-{d['index']}") or {}) if d["index"] is not None else {}
            if inst.get("host_port"):
                dus.append({**d, "host_port": inst["host_port"]})
            else:
                logger.warning("O1 skip DU %s of gnb %s: no host_port", d["me"], g.name)
        if not cu_port or not dus:
            logger.warning("O1 skip gnb %s: cu_port=%s dus=%d", g.name, cu_port, len(dus))
            continue
        p0, me = ports_for(g), me_names(g)
        base_labels = {"ransim.gnb": g.name, "ransim.meid": g.meid}
        # 多 DU(2026-10-01):一顆 facade 服務 CU-CP 加全部 DU 身分;DU_PORTS = "<telnet>:<gnb_du_id>:<DU URL>,..."
        du_ports = ",".join(f"{ports_for(g, d['k'])['facade_du']}:{d['gnb_du_id']}:http://127.0.0.1:{d['host_port']}" for d in dus)
        items.append({
            "key": f"o1facade-{g.e2_index}", "role": ROLE_FACADE, "name": f"o1facade-{rid}-{g.e2_index}",
            "image": O1_FACADE_IMAGE, "host_net": True, "labels": base_labels,
            "env": {"CU_URL": f"http://127.0.0.1:{cu_port}", "DU_URL": f"http://127.0.0.1:{dus[0]['host_port']}",
                    "GNB_NAME": g.meid, "VENDOR": "MITLAB RANsim-DT", "DU_CELL": "",
                    "CUCP_PORT": str(p0["facade_cucp"]), "DU_PORT": str(p0["facade_du"]), "DU_PORTS": du_ports},
        })

        def _adapter(unit, key, name_suffix, me_name, ports, telnet_port, gnb_du_id, model):
            return {
                "key": f"o1adapter-{key}-{g.e2_index}{name_suffix}", "role": ROLE_ADAPTER,
                "name": f"o1adapter-{key}-{rid}-{g.e2_index}{name_suffix}", "image": O1_ADAPTER_IMAGE, "host_net": False,
                "labels": {**base_labels, "ransim.o1_me": me_name},
                "ports": {"830/tcp": ports[0], "22/tcp": ports[1]},
                "env": {"O1_NODE_ID": me_name, "O1_UNIT_TYPE": unit, "O1_HOST": O1_HOST_IP,
                        "O1_NETCONF_PORT": str(ports[0]), "O1_SFTP_PORT": str(ports[1]),
                        "O1_TELNET_HOST": O1_HOST_IP, "O1_TELNET_PORT": str(telnet_port),
                        "O1_GNB_DU_ID": str(gnb_du_id), "O1_GNB_CU_ID": "0",
                        "O1_PM_INTERVAL": pm_interval, "O1_VES_URL": O1_VES_URL,
                        "O1_MODEL": model, "O1_LOCATION": f"DT run {rid} gnb {g.name}",
                        # SMO 的 ME 生命週期自動化(2026-09-30):pnfRegistration additionalFields 帶劇本資訊
                        "O1_SCENARIO_ID": scenario_id or "unknown", "O1_RUN_ID": run_tag, "O1_LIFECYCLE": "ephemeral"},
            }
        items.append(_adapter("CU-CP", "cucp", "", me["cucp"], (p0["cucp_netconf"], p0["cucp_sftp"]), p0["facade_cucp"], dus[0]["gnb_du_id"], "ransim-dt-cucp"))
        for d in dus:
            pk = ports_for(g, d["k"])
            items.append(_adapter("DU", "du", "" if d["k"] == 0 else f"-du{d['gnb_du_id']}", d["me"],
                                  (pk["du_netconf"], pk["du_sftp"]), pk["facade_du"], d["gnb_du_id"], "ransim-dt-du"))
    return items


def spawn(rid: str, scene_run_uuid: str, topo, instances: dict, scenario_id: str = "") -> list[dict]:
    """起 O1 容器;回傳已起清單(供寫通知)。任何錯誤只記 log,不讓 run 啟動失敗。"""
    if not O1_ENABLE:
        return []
    client = docker.from_env()
    started: list[dict] = []
    for it in plan(rid, topo, instances, scenario_id):
        try:
            try:
                old = client.containers.get(it["name"])
                old.remove(force=True)
            except docker.errors.NotFound:
                pass
            labels = {"ransim.scene_run_uuid": scene_run_uuid, "ransim.role": it["role"],
                      "ransim.instance": it["key"], **it["labels"]}
            net_kw = {"network_mode": "host"} if it["host_net"] else {"network": O1_NETWORK, "ports": it["ports"], "hostname": it["name"]}
            client.containers.run(it["image"], name=it["name"], detach=True, environment=it["env"], labels=labels,
                                  restart_policy={"Name": "unless-stopped"}, mem_limit="512m", memswap_limit="512m", **net_kw)
            started.append(it)
            logger.info("O1 started %s (%s)", it["name"], it["env"].get("O1_NODE_ID") or "facade")
        except Exception as exc:  # noqa: BLE001
            logger.exception("O1 start failed for %s: %s", it["name"], exc)
    _write_notice(rid, topo, started, "added")
    try:
        tag = next((it["env"].get("O1_RUN_ID") for it in started if it["env"].get("O1_RUN_ID")), "")
        if tag:
            _registry_append({"event": "start", "runId": tag, "rid": rid, "scene_run_uuid": scene_run_uuid,
                              "scenarioId": scenario_id or "unknown",
                              "mes": [{"gnb": g.name, "cucp": me_names(g)["cucp"], "du": me_names(g)["du"],
                                       "netconf_cucp": ports_for(g)["cucp_netconf"], "netconf_du": ports_for(g)["du_netconf"],
                                       "dus": [{"me": d["me"], "gnb_du_id": d["gnb_du_id"], "cells": d["cells"],
                                                "netconf": ports_for(g, d["k"])["du_netconf"]} for d in du_list(g)]}
                                      for g in topo.gnbs]})
    except Exception as exc:  # noqa: BLE001
        logger.warning("O1 run registry (start) failed: %s", exc)
    return started


def on_stop(rid: str, topo=None, scenario_id: str = "", final: bool = True) -> None:
    """run 收工時:先停 adapter,再替每個 ME 送 VES fault CLEAR,最後寫「移除 ME」通知。
    容器本身由 teardown 依標籤清掉。"""
    if not O1_ENABLE or topo is None:
        return
    # Preserve CM/FM state and PM values while sysrepo and /ftp still exist.
    try:
        from .o1_observation import snapshot_before_stop
        snapshot_before_stop(rid)
    except Exception as exc:  # noqa: BLE001 — monitoring cannot prevent shutdown
        logger.warning("O1 final observation failed: %s", exc)
    run_tag = _adapter_env(rid, "O1_RUN_ID") or rid   # 必須與 pnfRegistration 帶的 runId 相同;要在容器被清掉前讀
    # 2026-09-30:先停 adapter 再送 CLEAR。原本先送 CLEAR 再 teardown,CU / DU 比 adapter 早停,
    # adapter 會在被殺之前又發一筆 internalConnectionLoss,留在 SMO 告警清單清不掉(SMO PM-V1 回報)。
    try:
        _stop_adapters(rid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("O1 stop adapters failed: %s", exc)
    try:
        _send_clears(topo, rid=rid, run_id=run_tag)
    except Exception as exc:  # noqa: BLE001
        logger.warning("O1 stop clears failed: %s", exc)
    try:
        _registry_append({"event": "stop", "runId": run_tag, "rid": rid, "scenarioId": scenario_id or "unknown",
                          "reason": "normal" if final else "auto_restart"})
    except Exception as exc:  # noqa: BLE001
        logger.warning("O1 run registry (stop) failed: %s", exc)
    if not final:   # 自動重啟:ME 幾分鐘後以同一個 run 回來,不算下線 → 不送 notifyMOIDeletion、不寫移除通知
        logger.info("O1 stop for run %s is an auto-restart: skip notifyMOIDeletion and removal notice", rid)
        return
    try:
        _send_moi_deletions(run_tag, topo, scenario_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("O1 notifyMOIDeletion failed: %s", exc)
    try:
        _write_notice(rid, topo, None, "removed")
    except Exception as exc:  # noqa: BLE001
        logger.warning("O1 stop notice failed: %s", exc)


def _adapter_env(rid: str, key: str) -> str:
    """從該 run 的 adapter 容器環境變數取值(編排服務重啟後記憶體內的狀態會遺失,容器才是可靠來源)。"""
    try:
        for c in docker.from_env().containers.list(all=True, filters={"label": f"ransim.role={ROLE_ADAPTER}"}):
            if f"-{rid}-" in c.name:
                env = dict(e.split("=", 1) for e in c.attrs["Config"]["Env"] if "=" in e)
                return env.get(key, "")
    except Exception:  # noqa: BLE001
        pass
    return ""


def scenario_of(rid: str) -> str:
    return _adapter_env(rid, "O1_SCENARIO_ID")


def _registry_append(rec: dict) -> None:
    """run 對照表(2026-10-01):每次啟動 / 停止各寫一行 JSON 到 PER_RUN_LOG_DIR/_o1_run_registry.jsonl,長期保存。
    SMO 的 PM / 告警只帶 ME 名稱,而 ME 名稱會被不同 run、不同劇本重用;要以劇本為單位收資料,
    得靠這份「runId ↔ 劇本 ↔ ME ↔ 起訖時間」的對照。查詢工具:o1_smo_plan/02_測試/run_registry/run_registry.py。"""
    import json as _json
    d = pathlib.Path(getattr(settings, "PER_RUN_LOG_DIR", "/data/run_logs"))
    d.mkdir(parents=True, exist_ok=True)
    rec = {"ts": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **rec}
    with open(d / "_o1_run_registry.jsonl", "a", encoding="utf-8") as f:
        f.write(_json.dumps(rec, ensure_ascii=False) + "\n")


def _stop_adapters(rid: str) -> None:
    """只停不刪(log 落地與刪除仍由 teardown 做);並行停,避免 6 個 adapter 各等 10 秒。"""
    import time as _time
    from concurrent.futures import ThreadPoolExecutor
    cs = [c for c in docker.from_env().containers.list(filters={"label": f"ransim.role={ROLE_ADAPTER}"})
          if c.name.startswith("o1adapter-") and f"-{rid}-" in c.name]
    if not cs:
        return
    def _stop(c):
        try:
            c.stop(timeout=5)
        except Exception as exc:  # noqa: BLE001
            logger.warning("O1 adapter stop %s failed: %s", c.name, exc)
    with ThreadPoolExecutor(max_workers=len(cs)) as ex:
        list(ex.map(_stop, cs))
    logger.info("O1 adapters stopped for run %s: %d", rid, len(cs))
    _time.sleep(1.0)   # CLEAR 不可與 adapter 最後一筆事件同毫秒


def _send_clears(topo, rid: str = '', run_id: str = '') -> None:
    """對 run 內每個 ME 送 internalConnectionLoss 的 CLEAR(eventSeverity NORMAL),讓 SMO 的目前告警清單乾淨。"""
    import json as _json
    import time as _time
    import urllib.request as _ur
    seq = int(_time.time()) % 100000
    # (ME, alarmId, alarmType, probableCause):每個 ME 清 internalConnectionLoss;DU ME 另清 loadDownlinkExceededWarning
    # (2026-09-30:收工時負載告警若還掛著,adapter 已停、沒人清,會殘留在 SMO)。清一筆不存在的告警,SMO 端無副作用。
    targets = []
    for g in topo.gnbs:
        n = me_names(g)
        targets.append((n["cucp"], f"ManagedElement={n['cucp']}-internalConnectionLoss", "COMMUNICATIONS_ALARM", "COMMUNICATIONS_SUBSYSTEM_FAILURE"))
        for d in n["dus"]:   # 多 DU、多 cell(2026-10-01):每個 DU ME 一筆連線告警、每個 cell 一筆負載告警(probableCause 同 H4)
            targets.append((d["me"], f"ManagedElement={d['me']}-internalConnectionLoss", "COMMUNICATIONS_ALARM", "COMMUNICATIONS_SUBSYSTEM_FAILURE"))
            for lc in d["cells"]:
                targets.append((d["me"], f"ManagedElement={d['me']},GNBDUFunction={d['gnb_du_id']},NRCellDU={lc}-loadDownlinkExceededWarning",
                                "QUALITY_OF_SERVICE_ALARM", "THRESHOLD_CROSSED"))
    for me, alarm_id, alarm_type, cause in targets:
        if True:
            now = int(_time.time() * 1e6)
            iso = _time.strftime("%Y-%m-%dT%H:%M:%S.000Z", _time.gmtime())
            ev = {"event": {"commonEventHeader": {
                "domain": "stndDefined", "stndDefinedNamespace": "3GPP-FaultSupervision",
                "eventId": f"ManagedElement={me}_{cause}_runstop_{seq}",
                "eventName": "stndDefined_3GPP-FaultSupervision_NotifyClearedAlarm", "eventType": "3GPP-FaultSupervision",
                "sequence": seq, "priority": "Normal", "reportingEntityId": "", "reportingEntityName": me,
                "sourceId": me, "sourceName": me, "startEpochMicrosec": now, "lastEpochMicrosec": now,
                "nfNamingCode": "001", "nfVendorName": "MITLAB RANsim-DT", "timeZoneOffset": "+00:00",
                "version": "4.1", "vesEventListenerVersion": "7.2.1"},
                "stndDefinedFields": {"stndDefinedFieldsVersion": "1.0",
                    "schemaReference": "https://forge.3gpp.org/rep/sa5/MnS/blob/Rel-18/OpenAPI/TS28111_FaultNrm.yaml#components/schemas/NotifyClearedAlarm",
                    "data": {"href": f"/ManagedElement={me}", "notificationId": seq, "notificationType": "notifyClearedAlarm",
                             "eventTime": iso, "systemDN": f"ManagedElement={me}",
                             "alarmId": alarm_id,   # 與 adapter 發生時相同
                             "alarmType": alarm_type, "probableCause": cause,
                             "perceivedSeverity": "CLEARED", "clearUserId": "MITLAB RANsim-DT", "clearSystemId": "run-orchestrator"}}}}
            delivery_status = None
            try:
                req = _ur.Request(O1_VES_URL, data=_json.dumps(ev).encode(), headers={"Content-Type": "application/json"})
                with _ur.urlopen(req, timeout=8) as r:
                    delivery_status = r.status
                    logger.info("O1 clear sent for %s (%s) -> %s", me, cause, r.status)
            except Exception as exc:  # noqa: BLE001
                delivery_status = getattr(exc, 'code', None)
                logger.warning("O1 clear for %s failed: %s", me, exc)
            if rid and run_id:
                try:
                    from .o1_observation import record_delivery
                    record_delivery(rid, run_id, ev, delivery_status)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("O1 clear observation failed: %s", exc)


def _send_moi_deletions(rid: str, topo, scenario_id: str = "") -> None:
    """每個 ME 一筆 stndDefined / 3GPP-Provisioning 的 notifyMOIDeletion(TS 28.532),給 SMO 的 ME 生命週期控制器當反註冊訊號。
    必須是該 ME 在這個 run 的最後一筆事件(在 CLEAR 之後);runId 讓 SMO 分辨同名 ME 的不同 run。
    格式照 SMO 2026-09-30 驗證過的範例 DT_SMO_connect/02_測試/sample_stndDefined_notifyMOIDeletion.json。"""
    import json as _json
    import time as _time
    import urllib.request as _ur
    _time.sleep(1.0)   # 與 CLEAR 錯開,確保到達順序
    seq = int(_time.time()) % 100000
    for g in topo.gnbs:
        n = me_names(g)
        for me in [n["cucp"]] + [d["me"] for d in n["dus"]]:
            now = int(_time.time() * 1e6)
            attrs = {"runId": rid}
            if scenario_id:
                attrs["scenarioId"] = scenario_id
            ev = {"event": {"commonEventHeader": {
                "domain": "stndDefined", "stndDefinedNamespace": "3GPP-Provisioning",
                "eventName": "stndDefined_3GPP-Provisioning_NotifyMoiDeletion",
                "eventId": f"{me}-moiDeletion-{rid}", "sourceName": me, "sourceId": me,
                "reportingEntityName": f"ManagedElement={me}", "nfVendorName": "MITLAB RANsim-DT",
                "priority": "Normal", "sequence": seq, "startEpochMicrosec": now, "lastEpochMicrosec": now,
                "timeZoneOffset": "+00:00", "version": "4.1", "vesEventListenerVersion": "7.2.1"},
                "stndDefinedFields": {"stndDefinedFieldsVersion": "1.0",
                    "schemaReference": "https://forge.3gpp.org/rep/sa5/MnS/blob/Rel-18/OpenAPI/TS28532_ProvMnS.yaml#components/schemas/NotifyMoiDeletion",
                    "data": {"href": f"ManagedElement={me}", "notificationId": seq, "notificationType": "notifyMOIDeletion",
                             "eventTime": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()), "systemDN": f"ManagedElement={me}",
                             "sourceIndicator": "MANAGEMENT_OPERATION", "additionalText": f"run {rid} ended",
                             "attributeList": attrs}}}}
            try:
                req = _ur.Request(O1_VES_URL, data=_json.dumps(ev).encode(), headers={"Content-Type": "application/json"})
                with _ur.urlopen(req, timeout=8) as r:
                    logger.info("O1 notifyMOIDeletion sent for %s -> %s", me, r.status)
            except Exception as exc:  # noqa: BLE001
                logger.warning("O1 notifyMOIDeletion for %s failed: %s", me, exc)


def _write_notice(rid: str, topo, started, kind: str) -> None:
    d = pathlib.Path(getattr(settings, "PER_RUN_LOG_DIR", "/data/run_logs")) / rid / "o1"
    d.mkdir(parents=True, exist_ok=True)
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    title = "新增 ME" if kind == "added" else "移除 ME"
    lines = [f"# (DT) O1 {title} —— run {rid}", "", f"- 時間:{now}", f"- 動作:{'請把 meid 加進 PMS ric-dt-71 managedElementIds' if kind == 'added' else '請刪 SDNC mount(PMS managedElementIds 保留,slot 會重用)'}", "",
             "| meid(E2 / A1 / O1 CU-CP ME) | O1 DU ME | NETCONF CU-CP | NETCONF DU | SFTP CU-CP | SFTP DU |", "|---|---|---|---|---|---|"]
    for g in topo.gnbs:
        p, me = ports_for(g), me_names(g)
        for du in me["dus"]:   # 注意:不可用 d 當變數名,d 是上面的 Path
            pk = ports_for(g, du["k"])
            lines.append(f"| `{me['cucp']}` | `{du['me']}`(cells {du['cells']}) | {O1_HOST_IP}:{p['cucp_netconf']} | {O1_HOST_IP}:{pk['du_netconf']} | {p['cucp_sftp']} | {pk['du_sftp']} |")
    (d / f"notify_{kind}_{now.replace(':', '')}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # 給 TEIV 產生器用:meid → gNB-DU id(O1 的 _du<N>)
    import json as _json
    (d / "me_map.json").write_text(_json.dumps({g.meid: me_names(g)["gnb_du_id"] for g in topo.gnbs}, indent=1), encoding="utf-8")
