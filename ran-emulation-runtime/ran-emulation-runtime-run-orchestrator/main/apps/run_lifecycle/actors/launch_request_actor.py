"""LaunchRequest actors — Controller(create/update/delete)+ Reader(read)。全 POST(backend_rule §7-2)。"""
from __future__ import annotations

import json
import threading

from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.run_lifecycle.models.launch_request import LaunchRequest
from main.apps.run_lifecycle.serializers.launch_request_serializers import LaunchRequestReadSerializer, LaunchRequestWriteSerializer
from main.apps.run_lifecycle.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.run_lifecycle.services.common.timestamp_service import TimestampService
from main.apps.run_lifecycle.services.common.uuid_service import UUIDService
from django.conf import settings

from main.apps.run_lifecycle.services.optional import container_spawner, health_monitor, platform_clients
from main.apps.run_telemetry_archive.services.optional import cu_archiver
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)
UUID_FIELD = "launch_request_uuid"


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


_SLOT_LOCK = threading.Lock()   # E2 槽位配置序列化(同進程;orchestrator 單 worker)
_RUN_LOCKS: dict[str, threading.Lock] = {}
_RUN_LOCKS_GUARD = threading.Lock()


def _run_lock(run_uuid: str) -> threading.Lock:
    """同一 run 的 start / stop 序列化(2026-09-16:手動 stop/start 撞上自動復原的 stop/start → 兩邊各失敗一半,run 變 failed 無容器)。"""
    with _RUN_LOCKS_GUARD:
        return _RUN_LOCKS.setdefault(run_uuid, threading.Lock())

class LaunchRequestController:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def create(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        ser = LaunchRequestWriteSerializer(data=payload)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        now = TimestampService.get_current_timestamp()
        data = {UUID_FIELD: UUIDService.generate_uuid("launch_request"), "launch_request_created_at": now, "launch_request_updated_at": now, **ser.validated_data}
        entity = SqlDbBusinessService.create_entity(LaunchRequest, data)
        logger.info("launch_request created %s", getattr(entity, UUID_FIELD))
        return success_response(LaunchRequestReadSerializer(entity).data, "created", 201)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def update(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        uid = payload.pop(UUID_FIELD, None)
        if not uid:
            return error_response("Validation failed", {UUID_FIELD: "required"}, 400)
        entity = SqlDbBusinessService.get_or_none(LaunchRequest, UUID_FIELD, uid)
        if entity is None:
            return error_response("Not found", uid, 404)
        ser = LaunchRequestWriteSerializer(entity, data=payload, partial=True)
        if not ser.is_valid():
            return error_response("Validation failed", ser.errors, 400)
        data = {**ser.validated_data, "launch_request_updated_at": TimestampService.get_current_timestamp()}
        entity = SqlDbBusinessService.update_entity(LaunchRequest, UUID_FIELD, uid, data)
        return success_response(LaunchRequestReadSerializer(entity).data, "updated", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def delete(request):
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        uid = payload.get(UUID_FIELD)
        if not uid:
            return error_response("Validation failed", {UUID_FIELD: "required"}, 400)
        n = SqlDbBusinessService.delete_entity(LaunchRequest, UUID_FIELD, uid)
        if n == 0:
            return error_response("Not found", uid, 404)
        return success_response({"deleted": n}, "deleted", 200)


class LaunchRequestReader:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        """body 有 launch_request_uuid → 單筆;f_<parent>_uuid / 任一欄位 → 過濾列表;空 → 全部。"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        if UUID_FIELD in payload:
            entity = SqlDbBusinessService.get_or_none(LaunchRequest, UUID_FIELD, payload[UUID_FIELD])
            if entity is None:
                return error_response("Not found", payload[UUID_FIELD], 404)
            return success_response(LaunchRequestReadSerializer(entity).data, "ok", 200)
        filters = {}
        for k, v in payload.items():
            if k.startswith("f_") and k.endswith("_uuid"):
                # f_<fk_field>_uuid → <fk_field>__<parent_table>_uuid(用 model 元資料解析,支援同表多 FK)
                fk_name = k[2:-5]
                try:
                    fk = LaunchRequest._meta.get_field(fk_name)
                    filters[f"{fk_name}__{fk.target_field.name}"] = v
                except Exception:  # noqa: BLE001
                    filters[k] = v
            else:
                filters[k] = v
        qs = SqlDbBusinessService.list_entities(LaunchRequest, **filters)
        return success_response(LaunchRequestReadSerializer(qs, many=True).data, "ok", 200)


class LaunchController:
    """單 run 版(2026-09-13 P2):起/停一個 scene_run。
    P2 階段仍委派既有 UE driver 的 SimController(共用 CU/DU/RU 容器);P4 改為 spawn per-run 容器。"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def start(request):
        """body {scene_run_uuid, speed_x?, sim_dt_ms?}"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        run_uuid = str(payload.get("scene_run_uuid") or "")
        if not run_uuid:
            return error_response("Validation failed", {"scene_run_uuid": "required"}, 400)
        _lk = _run_lock(run_uuid); _lk.acquire()
        try:
            return LaunchController._start_locked(request, payload, run_uuid)
        finally:
            _lk.release()

    @staticmethod
    def _start_locked(request, payload, run_uuid):
        try:
            tree = platform_clients.read_full_tree(run_uuid)
        except Exception as exc:  # noqa: BLE001
            return error_response("registry unreachable or run not found", str(exc), 502)
        if not tree.get("success"):
            return error_response("scene_run not found", run_uuid, 404)
        t = tree["data"]; run = t.get("run") or {}

        def _run_knob(name: str):
            """run knob 取值(dict 或 [{key,value}] 兩種形狀都收)。

            2026-09-22:原本只在 per-run 分支裡有一份區域版本,
            但 ue_start 在那個分支外面也要用 —— 提到外層定義一次。
            """
            kn = run.get("knobs") or {}
            if isinstance(kn, dict):
                return kn.get(name)
            return next((k.get("value") for k in kn
                         if isinstance(k, dict) and k.get("key") == name), None)

        problems = []
        if not t.get("gnbs"):
            problems.append("scene has no gnb")
        if not t.get("ues"):
            problems.append("scene has no ue")
        for g in t.get("gnbs") or []:
            for du in g.get("dus") or []:
                for c in du.get("cells") or []:
                    if not c.get("ru"):
                        problems.append(f"cell {c.get('name')} has no ru")
        if problems:
            return error_response("scene incomplete", problems, 400)
        speed_x = float(payload.get("speed_x") or run.get("speed_x") or 1.0)
        sim_dt_ms = int(payload.get("sim_dt_ms") or run.get("sim_dt_ms") or 500)
        now = TimestampService.get_current_timestamp()
        req_row = SqlDbBusinessService.create_entity(LaunchRequest, {
            UUID_FIELD: UUIDService.generate_uuid("launch_request"), "launch_request_created_at": now, "launch_request_updated_at": now,
            "f_scene_run_uuid": run_uuid, "action": "start", "mode": str(run.get("mode") or "cached"), "speed_x": speed_x, "status": "accepted"})
        try:
            ue_host = None; cu_host = None; e2_port = None; instances: dict[str, dict] = {}; e2_node = ""; gnb_id_hex = ""
            if settings.PER_RUN_ENABLED:
                mode = str(run.get("mode") or "cached")
                if mode == "live" and container_spawner.live_run_exists(run_uuid):
                    raise RuntimeError("live 模式同時只允許 1 個 run(Physics/GPU 共用);請用 cached 或先停另一個 live run")
                # 舊的 run_instance 列清掉(重跑)
                for old in platform_clients.list_run_instances(run_uuid):
                    platform_clients.delete_run_instance(old["run_instance_uuid"])
                # E2 node 身分:從執行中 run 的 e2_node_id 反推已用槽位,配一個沒人用的(RIC 以 PLMN+gNB ID 當 meid)
                # 2026-09-16 事故:docker 重啟後兩個 run 同時自動重啟,都看到對方「不是 running」→ 都拿到槽位 1(同 meid、adapter port 撞)。
                # 配槽位 + 立刻把 gnb_id_hex/status=starting 寫回 registry 要在同一把鎖內;used 也把 starting 算進去。
                # 2026-09-22:場域若釘了 e2_slot 就一律用它。外部 Agent 會依 I-2 回報的
                # gNB ID / cell NCI 去部署 xApp(訂閱與 control 都用 meid + NCI 定位),
                # 槽位浮動 = 識別浮動 = xApp 訂不到。代價是同一場域同時只能跑一場。
                pinned = (t.get("scene") or {}).get("e2_slot")
                with _SLOT_LOCK:
                    used = [r.get("gnb_id_hex") or "" for st in ("running", "starting")
                            for r in platform_clients.list_runs_by_status(st) if r.get("scene_run_uuid") != run_uuid]
                    if pinned:
                        taken = {int(h, 16) & container_spawner.GNB_ID_SLOTS for h in used if h}
                        if int(pinned) in taken:
                            raise RuntimeError(
                                f"場域已釘 E2 槽位 {pinned},但該槽位正被另一個 run 占用 —— "
                                f"同一場域同時只能跑一場(識別要固定給 xApp 用);請先停掉另一場")
                        slot = int(pinned)
                    else:
                        # 動態分配要避開所有被釘住的號碼(見 allocate_slot 的說明)
                        reserved = set()
                        try:
                            for sc in (platform_clients.list_scenes() or {}).get("data") or []:
                                if sc.get("e2_slot"):
                                    reserved.add(int(sc["e2_slot"]))
                        except Exception:  # noqa: BLE001 — 查不到就退回舊行為,不擋啟動
                            logger.warning("讀取已釘槽位失敗,動態分配可能與釘住的場域衝突")
                        slot = container_spawner.allocate_slot(used, reserved)
                    gnb_id_hex = container_spawner.gnb_id_hex_for_slot(slot)
                    e2_node = container_spawner.e2_node_name(gnb_id_hex)
                    platform_clients.update_scene_run(run_uuid, status="starting", gnb_id_hex=gnb_id_hex, e2_node_id=e2_node)
                # 兩階段:先 cu/du/ru/ue → 等健康 → 再起 e2adapter(它啟動就抓 CU 的 E2 node id 送 E2 Setup,CU 要先 ready)
                def _register(spawned: dict[str, dict]) -> None:
                    for role, info in spawned.items():
                        r = platform_clients.create_run_instance(run_uuid, role, info["container_id"], info["host_port"])
                        instances[role] = {**info, "run_instance_uuid": (r.get("data") or {}).get("run_instance_uuid")}
                # DU 設定從 registry 的模板 + 每 DU 覆寫來(第一個 gNB 的第一個 DU;多 DU 場景先取第一個)
                _du = next((d for g in (t.get("gnbs") or []) for d in (g.get("dus") or [])), {})
                du_env = container_spawner.du_env_from_template(_du.get("config_template"), _du.get("config_override"))
                if du_env:
                    logger.info("run %s DU 設定注入: %s", run_uuid, du_env)
                # run knob `anr_auto_add`:CU 要不要從量測報告自己學鄰區關係。
                # 走廊這種「每個 cell 各自一個 gNB」的場景,跨 gNB 關係不會自動種,
                # 沒有 RIC 的 xApp 補的話 A3 會被 NRT gate 全部擋掉(實測一場 7 萬次)。
                # 跑 RIC 的 ANR 驗證時要關,否則關係自己長出來、他們的 anr-add 看不出效果。
                _knobs0 = run.get("knobs") or {}

                def _knob(name: str):
                    if isinstance(_knobs0, dict):
                        return _knobs0.get(name)
                    return next((k.get("value") for k in _knobs0
                                 if isinstance(k, dict) and k.get("key") == name), None)

                def _on(v) -> str:
                    return "1" if str(v).strip().lower() in ("1", "on", "true", "yes") else "0"

                cu_env = {}
                _auto = _knob("anr_auto_add")
                if _auto is not None:
                    cu_env["ANR_AUTO_ADD"] = _on(_auto)
                # run knob `anr_pci_lookup`:CU 改用「只認 PCI、查不到才解析 CGI」的真實流程。
                # 開啟會讓缺漏鄰區與 PCI 混淆真的發生 —— 也就會改變既有場景的換手時機,
                # 所以預設關閉,只有要出這類題目的場景才打開。
                _pci = _knob("anr_pci_lookup")
                if _pci is not None:
                    cu_env["ANR_PCI_LOOKUP"] = _on(_pci)
                # CGI 解析失敗率(模擬訊號太弱讀不到 SIB1);決定性,同參數重跑結果相同
                _fail = _knob("anr_cgi_fail_rate")
                if _fail is not None:
                    cu_env["ANR_CGI_FAIL_RATE"] = str(_fail)
                # 2026-09-22 外部 Agent 規格總則 7:run 級 seed。混進 slot 引擎的 RNG,
                # 同 seed 重跑逐 tick 重現,換 seed 得到另一組雜訊實現。
                # 不給就是 0 —— 與加這個旋鈕之前的行為完全相同。
                _seed = _knob("run_seed")
                if _seed is not None:
                    du_env = {**(du_env or {}), "RUN_SEED": str(int(_seed))}
                _register(container_spawner.spawn(run_uuid, mode, gnb_id_hex=gnb_id_hex, slot=slot, roles=("cu", "du", "ru", "ue"), du_env=du_env, cu_env=cu_env))
                health = container_spawner.wait_healthy(instances)
                if not all(health.values()):
                    raise RuntimeError(f"per-run 容器未就緒: {health}")
                _register(container_spawner.spawn(run_uuid, mode, slot=slot, roles=("e2adapter",), cu_host_port=instances["cu"]["host_port"]))
                health = container_spawner.wait_healthy({"e2adapter": instances["e2adapter"]}, timeout_sec=90)
                if not all(health.values()):
                    raise RuntimeError(f"e2adapter 未就緒: {health}")
                ue_host = instances["ue"]["name"]; cu_host = instances["cu"]["name"]; e2_port = instances["e2adapter"]["host_port"]
                health_monitor.start_monitor(run_uuid, instances)
            # run knob `ue_limit`:外部 Agent 的 I-3 ue_count。只能往下裁(見 subset_ues);
            # 沒給就是整個劇本的人,與加這個旋鈕之前完全相同。
            _ue_limit = _run_knob("ue_limit")
            ue = platform_clients.ue_start(
                run_uuid, speed_x, sim_dt_ms, host=ue_host,
                ue_limit=int(_ue_limit) if _ue_limit else None,
                ue_seed=int(_run_knob("run_seed") or 0))
            ok = bool(ue.get("success"))
            SqlDbBusinessService.update_entity(LaunchRequest, UUID_FIELD, getattr(req_row, UUID_FIELD),
                                               {"status": "started" if ok else "failed", "detail": ue, "launch_request_updated_at": TimestampService.get_current_timestamp()})
            if ok:
                platform_clients.update_scene_run(run_uuid, status="running", speed_x=speed_x, sim_dt_ms=sim_dt_ms, started_at=now.isoformat(),
                                                  **({"e2_node_id": e2_node, "gnb_id_hex": gnb_id_hex} if settings.PER_RUN_ENABLED else {}))
                # run knob `ric_purpose`(例:validation)→ 閘道 labels.purpose,決定 RIC 要不要主動探測
                _ric_run = 0          # RIC 閘道宣告回應的 `run` 場次號(見下方)
                _knobs = run.get("knobs") or {}
                _ric_purpose = str((_knobs.get("ric_purpose") if isinstance(_knobs, dict)
                                    else next((k.get("value") for k in _knobs if isinstance(k, dict) and k.get("key") == "ric_purpose"), "")) or "")
                if settings.PER_RUN_ENABLED and e2_node:   # RIC 場景閘道:宣告場景 + 它唯一的 meid(best effort)
                    gw = platform_clients.ric_register_scenario(run_uuid, str((t.get("scene") or {}).get("legacy_scenario_id") or (t.get("scene") or {}).get("name") or ""), e2_node, gnb_id_hex=gnb_id_hex, purpose=_ric_purpose)
                    logger.info("RIC gateway register %s → %s", e2_node, gw)
                    # 2026-09-19 RIC 端請求:記下他們的場次號,兩邊對資料不用換算(InfluxDB `run` 標籤就是這個)
                    if isinstance(gw, dict):
                        try:
                            _ric_run = int(gw.get("run") or (gw.get("data") or {}).get("run") or 0)
                        except (TypeError, ValueError):
                            _ric_run = 0
                    if settings.RIC_GATEWAY_DEPLOY_XAPP and gw and not gw.get("error"):   # 專屬 xApp pod;RIC 端 dt-anr 參數化前先關(env)
                        xa = platform_clients.ric_deploy_xapp(run_uuid)
                        logger.info("RIC gateway xapp deploy %s → %s", run_uuid, str(xa)[:200])
                    if gw and not gw.get("error"):   # 閘道 0.8.4:E2 Setup 完成後啟用,之後才能經閘道下控制
                        import threading as _th
                        _th.Thread(target=platform_clients.ric_activate_when_ready, args=(run_uuid,),
                                   name=f"ric-activate-{run_uuid[-8:]}", daemon=True).start()
                # 啟動新的一輪 = 上一輪已經用完 —— 這時候清過期歸檔最安全
                # (跑完就清會讓外部 Agent 來不及 pull;見 archive_retention 的說明)
                from main.apps.run_telemetry_archive.services.optional import archive_retention
                _purged = archive_retention.apply_on_start(run_uuid)
                if _purged:
                    logger.info("run %s 啟動前歸檔清理: %s", run_uuid, _purged)
                cu_archiver.start_archiver(run_uuid, sim_dt_ms, cu_host=cu_host, e2_port=e2_port, ric_run=_ric_run)   # P2-3:run 期間封存 CU 落地表(P4-1:per-run CU)
            else:
                platform_clients.update_scene_run(run_uuid, status="failed", notes=str(ue.get("message") or "")[:500])
                return error_response("UE driver refused start", ue, 502)
        except Exception as exc:  # noqa: BLE001
            logger.exception("launch start failed run=%s", run_uuid)
            if settings.PER_RUN_ENABLED:
                health_monitor.stop_monitor(run_uuid)
                try:
                    container_spawner.teardown(run_uuid)
                except Exception:  # noqa: BLE001
                    logger.exception("teardown after failed start %s", run_uuid)
            SqlDbBusinessService.update_entity(LaunchRequest, UUID_FIELD, getattr(req_row, UUID_FIELD), {"status": "failed", "detail": {"error": str(exc)}})
            try:
                platform_clients.update_scene_run(run_uuid, status="failed", notes=str(exc)[:500])
            except Exception:  # noqa: BLE001
                pass
            return error_response("launch failed", str(exc), 502)
        logger.info("run %s started (speed %.2fx, sim_dt %d)", run_uuid, speed_x, sim_dt_ms)
        return success_response({"scene_run_uuid": run_uuid, "speed_x": speed_x, "sim_dt_ms": sim_dt_ms, "ue": ue.get("data"), "e2_node_id": e2_node, "gnb_id_hex": gnb_id_hex, "instances": {r: {k: v for k, v in i.items() if k != "run_instance_uuid"} for r, i in instances.items()}}, "started", 201)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def stop(request):
        """body {scene_run_uuid}"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        run_uuid = str(payload.get("scene_run_uuid") or "")
        if not run_uuid:
            return error_response("Validation failed", {"scene_run_uuid": "required"}, 400)
        _lk = _run_lock(run_uuid); _lk.acquire()
        try:
            return LaunchController._stop_locked(request, payload, run_uuid)
        finally:
            _lk.release()

    @staticmethod
    def _stop_locked(request, payload, run_uuid):
        now = TimestampService.get_current_timestamp()
        req_row = SqlDbBusinessService.create_entity(LaunchRequest, {
            UUID_FIELD: UUIDService.generate_uuid("launch_request"), "launch_request_created_at": now, "launch_request_updated_at": now,
            "f_scene_run_uuid": run_uuid, "action": "stop", "status": "accepted"})
        try:
            ue_host = container_spawner.names_for(run_uuid)["ue"] if settings.PER_RUN_ENABLED else None
            try:
                ue = platform_clients.ue_stop(host=ue_host)
            except Exception as exc:  # noqa: BLE001
                ue = {"success": False, "message": f"ue_stop: {exc}"}   # 容器可能已死;照樣往下清
            archive_stats = cu_archiver.stop_archiver(run_uuid)
            containers = None
            if settings.PER_RUN_ENABLED:
                health_monitor.stop_monitor(run_uuid)
                containers = container_spawner.teardown(run_uuid)
                for inst in platform_clients.list_run_instances(run_uuid):
                    platform_clients.update_run_instance(inst["run_instance_uuid"], status="stopped")
            platform_clients.update_scene_run(run_uuid, status="stopped", stopped_at=now.isoformat())
            ric_note = None
            if settings.PER_RUN_ENABLED:   # 收尾第 4 步:SCTP 已關 → 解除場景 → 清 R-NIB(RIC 場景閘道;沒設就只記 log)
                try:
                    rr = platform_clients._registry("Simulation_run/SceneRunReader/read", {"scene_run_uuid": run_uuid}).get("data") or {}
                    if rr.get("e2_node_id"):
                        platform_clients.notify_ric_stopped(run_uuid, rr["e2_node_id"], rr.get("gnb_id_hex") or "")   # 舊 webhook(可選)
                        # RIC 端(2026-09-14):DELETE /v1/scenarios/{id} 一次做「釋放 meid 綁定 + 清 R-NIB 三樣」;放最後(容器已停、SCTP 已斷)。
                        # 只有 DELETE 沒清成(404 / cleared:false)才補呼 /v1/rnib/clear。
                        ric_note = platform_clients.ric_unregister_scenario(run_uuid)
                        purged = bool(ric_note) and not ric_note.get("error") and all(x.get("cleared") for x in (ric_note.get("rnibPurge") or [])) and bool(ric_note.get("rnibPurge"))
                        if not purged:
                            ric_note = {"delete": ric_note, "rnib_clear": platform_clients.ric_rnib_clear(rr["e2_node_id"], rr.get("gnb_id_hex") or "")}
                except Exception as exc:  # noqa: BLE001
                    logger.warning("RIC cleanup failed: %s", exc)
            SqlDbBusinessService.update_entity(LaunchRequest, UUID_FIELD, getattr(req_row, UUID_FIELD),
                                               {"status": "stopped", "detail": ue, "launch_request_updated_at": TimestampService.get_current_timestamp()})
        except Exception as exc:  # noqa: BLE001
            logger.exception("launch stop failed run=%s", run_uuid)
            return error_response("stop failed", str(exc), 502)
        return success_response({"scene_run_uuid": run_uuid, "ue": ue.get("data"), "archive": archive_stats, "containers": containers, "ric_notified": ric_note}, "stopped", 200)
