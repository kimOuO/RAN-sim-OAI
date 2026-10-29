"""LaunchRequest actors — Controller(create/update/delete)+ Reader(read)。全 POST(backend_rule §7-2)。"""
from __future__ import annotations

import os

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

from main.apps.run_lifecycle.services.optional import container_spawner, health_monitor, platform_clients, o1_spawner
from main.apps.run_telemetry_archive.services.optional import cu_archiver
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)

# live 模式的倍速上限(cached 不受此限)。實測見 2026-09-22 的量測:
# 走廊場景設 10x 只達成 5.8~6.5x,且其中約七成 tick 是 RU 位置量化快取命中的。
# 取 2x 是保守值 —— 確保各種場景都跟得上,劇本時鐘不會與牆鐘脫節。
LIVE_MAX_SPEED_X = 2.0
# cached 模式上限。2026-09-22 實測走廊 30x:在場 UE 到 14 人時 DU 過載,RU→DU 的同步回呼
# 互等把整場拖進 RLF 風暴(達成率 0.7x、10 分鐘 731 次假 RLF),資料整場作廢。
# 早上同場景 30x 也只達成 6x。10x 是有餘裕且資料正確的上限。
CACHED_MAX_SPEED_X = 10.0
UUID_FIELD = "launch_request_uuid"


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


_SLOT_LOCK = threading.Lock()
_O1_TOPO: dict[str, tuple] = {}   # run → (rid, topo),給 O1 收工通知用(2026-09-29)
_DEFERRED: dict[str, dict] = {}   # run → 延後起的 e2adapter(驗收 18)   # E2 槽位配置序列化(同進程;orchestrator 單 worker)
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
        """body {scene_run_uuid, speed_x?, sim_dt_ms?, no_ric?}

        no_ric=true:DT 內部整合測試用 —— 不起 e2adapter、不向 RIC 閘道宣告/部署/啟用,
        RIC 完全看不到這一場(RIC 端要求:每次起場景前先約時間;內部測試不該碰到他們)。"""
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
        if run.get('status') == 'precomputing':
            return error_response('通道快取預算中，完成後才能啟動', run_uuid, 409)

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
        # 2026-09-22 live 模式倍速上限。
        # live 每個 tick 都要即時射線追蹤,實測走廊場景設 10x 只達成 5.8~6.5x,
        # 而且那六成多還是靠 RU 的位置量化快取撐的 —— 換成移動快的場景會更低。
        # 達不到的倍速會讓劇本時鐘與牆鐘脫節(事件時間、KPM 視窗都跟著失準),
        # 所以寧可設一個保守且跟得上的上限,而不是讓使用者設一個做不到的數字。
        _mode = str(run.get("mode") or "cached")
        # 2026-09-28:沒預算也能啟動 —— cached 場景找不到通道快取檔時改用 live(即時算通道),倍速 1×。
        # 「有沒有預算」是場景屬性、不是狀態;預算好的場景才能跑到 cached 上限。
        from main.apps.run_lifecycle.services.optional import channel_cache
        if _mode == "cached" and channel_cache.available(t.get("scene") or {}):
            cache = channel_cache.inspect_cache(t)
            if not cache['valid']:
                return error_response("通道快取已過期，請重新預算", cache, 409)
        if _mode == "cached" and not channel_cache.available(t.get("scene") or {}):
            logger.info("run %s:場景 %s 沒有預算快取 → 改用 live 1×", run_uuid, channel_cache.scenario_id(t.get("scene") or {}))
            _mode = "live"
            speed_x = min(speed_x, 1.0)
        _cap = LIVE_MAX_SPEED_X if _mode == "live" else CACHED_MAX_SPEED_X
        if speed_x > _cap:
            logger.info("run %s %s 模式倍速自 %.1fx 降為上限 %.1fx", run_uuid, _mode, speed_x, _cap)
            speed_x = _cap
        sim_dt_ms = int(payload.get("sim_dt_ms") or run.get("sim_dt_ms") or 500)
        if not 10 <= sim_dt_ms <= 500:
            return error_response("Validation failed", {"sim_dt_ms": "必須介於 10 與 500 ms"}, 400)
        no_ric = bool(payload.get("no_ric"))
        # 驗收 18 用:這些 gNB(nodeId)的 e2adapter 先不起,activate 也先不打;
        # 之後由 LaunchController/start_e2adapter 補起並 activate
        defer_nodes = {str(x) for x in (payload.get("defer_e2_nodes") or [])}
        now = TimestampService.get_current_timestamp()
        req_row = SqlDbBusinessService.create_entity(LaunchRequest, {
            UUID_FIELD: UUIDService.generate_uuid("launch_request"), "launch_request_created_at": now, "launch_request_updated_at": now,
            "f_scene_run_uuid": run_uuid, "action": "start", "mode": _mode, "speed_x": speed_x, "status": "accepted"})
        _ric_gw = None        # 閘道宣告結果(起不來時要撤回)
        try:
            ue_host = None; cu_host = None; e2_port = None; instances: dict[str, dict] = {}; e2_node = ""; gnb_id_hex = ""
            _ric_run = 0          # RIC 閘道宣告回應的 `run` 場次號(見下方)
            if settings.PER_RUN_ENABLED:
                mode = _mode
                if mode == "live" and container_spawner.live_run_exists(run_uuid):
                    raise RuntimeError("live 模式同時只允許 1 個 run(Physics/GPU 共用);請用 cached 或先停另一個 live run")
                # 舊的 run_instance 列清掉(重跑)
                for old in platform_clients.list_run_instances(run_uuid):
                    platform_clients.delete_run_instance(old["run_instance_uuid"])
                # ── E2 區塊(計畫 D3):一場配一個區塊 b(1–15),第 i 個 gNB 的 gNB ID = 0xe00 | (16b + i)。
                # 配區塊 + 立刻寫回 registry 在同一把鎖內(2026-09-16 事故:兩個 run 同時自動重啟搶到同號)。
                # 場域釘了 e2_block 就一律用它(外部 Agent 依 I-2 回報的身分部署 xApp,身分不可浮動)。
                pinned = (t.get("scene") or {}).get("e2_block")
                from ran_sim_protocol import e2_identity as _ident
                from ran_sim_protocol.run_topology import build_from_tree, default_names
                with _SLOT_LOCK:
                    used = {int(r["e2_block"]) for st in ("running", "starting")
                            for r in platform_clients.list_runs_by_status(st)
                            if r.get("scene_run_uuid") != run_uuid and r.get("e2_block")}
                    if pinned:
                        if int(pinned) in used:
                            raise RuntimeError(
                                f"場域已釘 E2 區塊 {pinned},但該區塊正被另一個 run 占用 —— "
                                f"同一場域同時只能跑一場(識別要固定給 xApp 用);請先停掉另一場")
                        block = int(pinned)
                    else:
                        reserved = set()
                        try:
                            for sc in (platform_clients.list_scenes() or {}).get("data") or []:
                                if sc.get("e2_block"):
                                    reserved.add(int(sc["e2_block"]))
                        except Exception:  # noqa: BLE001 — 查不到就不避,不擋啟動
                            logger.warning("讀取已釘區塊失敗,動態分配可能與釘住的場域衝突")
                        free = [b for b in range(_ident.BLOCK_MIN, _ident.BLOCK_MAX + 1) if b not in used | reserved]
                        if not free:
                            raise RuntimeError("E2 區塊用完(同時最多 15 場)")
                        block = free[0]
                    topo = build_from_tree(t, run_uuid=run_uuid, block=block,
                                           names=default_names(container_spawner.rid_of(run_uuid)),
                                           e2_port_base=container_spawner.E2ADAPTER_PORT_BASE)
                    if len(topo.gnbs) > _ident.BLOCK_SIZE:
                        raise RuntimeError(f"一場最多 {_ident.BLOCK_SIZE} 個 gNB,本場景有 {len(topo.gnbs)} 個")
                    e2_nodes = [] if no_ric else [{
                        "node_id": g.name, "e2_index": g.e2_index, "slot": _ident.slot_for(block, g.e2_index),
                        "gnb_id": g.gnb_id, "gnb_id_hex": g.gnb_id_hex, "meid": g.meid, "cell_tag": g.cell_tag,
                        "plmn_mcc": g.mcc, "plmn_mnc": g.mnc, "plmn_bcd": g.plmn_bcd, "gnb_id_bits": g.gnb_id_bits,
                        "cells": [{"cell_id": c.cell_id, "nci": c.nci, "ncgi": c.ncgi, "pci": c.pci} for d in g.dus for c in d.cells],
                    } for g in topo.gnbs]
                    g0 = topo.gnbs[0]
                    gnb_id_hex = g0.gnb_id_hex
                    e2_node = "" if no_ric else g0.meid   # 過渡欄位(舊的單 node 消費端);多 node 以 e2_nodes 為準
                    platform_clients.update_scene_run(run_uuid, status="running", last_result="", e2_block=block, e2_nodes=e2_nodes,
                                                      gnb_id_hex=gnb_id_hex, e2_node_id=e2_node)
                logger.info("run %s 區塊 %d:%s", run_uuid, block,
                            ", ".join(f"{g.name}={g.meid}({len(g.dus)} DU)" for g in topo.gnbs))

                def _register(spawned: dict[str, dict]) -> None:
                    gnb_uuid = {g.name: g.gnb_uuid for g in topo.gnbs}
                    du_uuid = {d.name: d.du_uuid for d in topo.dus()}
                    meid = {g.name: g.meid for g in topo.gnbs}
                    for key, info in spawned.items():
                        r = platform_clients.create_run_instance(
                            run_uuid, info["role"], info["container_id"], info["host_port"], name=info["name"],
                            gnb_uuid=gnb_uuid.get(info.get("gnb") or ""), du_uuid=du_uuid.get(info.get("du") or ""),
                            e2_node_id=(meid.get(info.get("gnb") or "") if info["role"] in ("cu", "e2adapter") and not no_ric else ""))
                        instances[key] = {**info, "run_instance_uuid": (r.get("data") or {}).get("run_instance_uuid")}

                # DU 設定:每個 DU 各自的 registry 模板 + 覆寫(以前只取第一個 DU 套到唯一的 DU)
                _knobs0 = run.get("knobs") or {}

                def _knob(name: str):
                    if isinstance(_knobs0, dict):
                        return _knobs0.get(name)
                    return next((k.get("value") for k in _knobs0
                                 if isinstance(k, dict) and k.get("key") == name), None)

                def _on(v) -> str:
                    return "1" if str(v).strip().lower() in ("1", "on", "true", "yes") else "0"

                # 2026-09-22 外部 Agent 規格總則 7:run 級 seed(混進 slot 引擎 RNG;0 = 加旋鈕前的行為)
                _seed = _knob("run_seed")
                du_envs: dict[str, dict[str, str]] = {}
                for g in t.get("gnbs") or []:
                    for d in g.get("dus") or []:
                        env = container_spawner.du_env_from_template(d.get("config_template"), d.get("config_override"))
                        if _seed is not None:
                            env["RUN_SEED"] = str(int(_seed))
                        du_envs[f"{g['name']}/{d.get('name')}"] = env
                # CU:run knob(ANR 行為)全場一致;PLMN / gNB ID 由拓樸逐 gNB 帶
                cu_env: dict[str, str] = {}
                # run knob `anr_auto_add`:CU 要不要從量測報告自己學鄰區關係(跑 RIC 的 ANR 驗證時要關)
                if _knob("anr_auto_add") is not None:
                    cu_env["ANR_AUTO_ADD"] = _on(_knob("anr_auto_add"))
                # run knob `anr_pci_lookup`:只認 PCI、查不到才解析 CGI 的真實流程(預設關)
                if _knob("anr_pci_lookup") is not None:
                    cu_env["ANR_PCI_LOOKUP"] = _on(_knob("anr_pci_lookup"))
                # CGI 解析失敗率(模擬訊號太弱讀不到 SIB1);決定性,同參數重跑結果相同
                if _knob("anr_cgi_fail_rate") is not None:
                    cu_env["ANR_CGI_FAIL_RATE"] = str(_knob("anr_cgi_fail_rate"))
                # 2026-09-23:鄰區量測以 PCI@ARFCN 為鍵;全域由 orchestrator env E2_NEIGHBOR_KEY 決定
                cu_env["E2_NEIGHBOR_KEY"] = os.environ.get("E2_NEIGHBOR_KEY", "pci").strip().lower()
                # 多 gNB P6:Xn 不可用時改走 NG 換手(經 AMF);預設關 = 維持「沒有 Xn → TXnRELOCprepExpiry」
                if _knob("ho_ng_fallback") is not None:
                    cu_env["HO_NG_FALLBACK"] = "on" if _on(_knob("ho_ng_fallback")) == "1" else "off"
                # 新增鄰區後 gNB 是否自動經 Xn 建反向關係、標 xnX2Established(預設開;關掉可做「有關係但沒 Xn」的題目)
                if _knob("anr_xn_auto_reverse") is not None:
                    cu_env["ANR_XN_AUTO_REVERSE"] = "on" if _on(_knob("anr_xn_auto_reverse")) == "1" else "off"
                cu_envs = {g.name: dict(cu_env) for g in topo.gnbs}
                # run knob `fullkpm_v2`:這場的 E2 adapter 在 E2 Setup 另外宣告 DT 完整 KPM v2(func 7,OID / 分塊合規版)。
                # 只影響這一場;func 5 照舊宣告。預設不帶 = 模板的 off。
                e2_env: dict[str, str] = {}
                if _knob("fullkpm_v2") is not None:
                    e2_env["E2SM_FULLKPM2_ENABLE"] = "on" if _on(_knob("fullkpm_v2")) == "1" else "off"
                # run knob `fullkpm_v2_dump`:驗證用,func 7 每則送出的原始位元組寫到 E2Adapter/logs/fullkpm2_dump_*.jsonl
                if _knob("fullkpm_v2_dump") is not None:
                    e2_env["E2SM_FULLKPM2_DUMP"] = "on" if _on(_knob("fullkpm_v2_dump")) == "1" else "off"
                # run knob `anr_v2` / `anr_v2_dump`:同上,針對 E2SM-ANR v2(func 8)
                if _knob("anr_v2") is not None:
                    e2_env["E2SM_ANR2_ENABLE"] = "on" if _on(_knob("anr_v2")) == "1" else "off"
                if _knob("anr_v2_dump") is not None:
                    e2_env["E2SM_ANR2_DUMP"] = "on" if _on(_knob("anr_v2_dump")) == "1" else "off"

                # ── RIC 閘道(計畫 D4 順序):先綁全部 node、部署 xApp,之後才起 e2adapter 做 E2 Setup ——
                # 否則 RIC 常駐 xApp 會先接手還沒綁定的 meid。
                _ric_purpose = str(_knob("ric_purpose") or "")
                if not no_ric:
                    nodes = [{"nodeId": g.name, "meid": g.meid, "plmnId": g.plmn_bcd, "nbIdBits": g.gnb_id_bits}
                             for g in topo.gnbs]
                    scene_name = str((t.get("scene") or {}).get("legacy_scenario_id") or (t.get("scene") or {}).get("name") or "")
                    _ric_gw = platform_clients.ric_register_nodes_with_retry(run_uuid, scene_name, nodes, purpose=_ric_purpose)
                    logger.info("RIC gateway register %s nodes=%s → %s", run_uuid, [n["meid"] for n in nodes], _ric_gw)
                    if isinstance(_ric_gw, dict):
                        try:   # 2026-09-19 RIC 端請求:記下他們的場次號(InfluxDB `run` 標籤)
                            _ric_run = int(_ric_gw.get("run") or (_ric_gw.get("data") or {}).get("run") or 0)
                        except (TypeError, ValueError):
                            _ric_run = 0
                    if settings.RIC_GATEWAY_DEPLOY_XAPP and _ric_gw and not _ric_gw.get("error"):
                        # xApp 的 env 隨場次帶(run knob `xapp_env`)。
                        # 2026-09-28(RIC 決定):RIC 端 guard 與 gNB 的 anr_auto_add 解耦 —— guard 是 SON 閉環本體,
                        # 自己會讀 gNB 的 ANR 狀態;只有場景明確設獨立 knob `ric_guard=0` 才關。以前 anr_auto_add=0 會連帶關 guard。
                        _xenv: dict = {}
                        try:
                            _xenv = dict(json.loads(_run_knob("xapp_env") or "{}") or {})
                        except (TypeError, ValueError):
                            logger.warning("run knob xapp_env 不是 JSON 物件,忽略")
                        if str(_run_knob("ric_guard") or "").strip() == "0":
                            _xenv.setdefault("ANR_GUARD_ENABLE", "0")
                        xa = platform_clients.ric_deploy_xapp(run_uuid, env=_xenv or None)
                        logger.info("RIC gateway xapp deploy %s → %s", run_uuid, str(xa)[:200])

                # ── 起容器:核心(AMF / CU / DU / RU / UE)→ 等健康 → e2adapter(抓 CU 的 E2 node id 做 E2 Setup)
                plan = container_spawner.plan_instances(run_uuid, topo, no_ric=no_ric, du_envs=du_envs, cu_envs=cu_envs, e2_env=e2_env,
                                                        with_amf=settings.PER_RUN_AMF_ENABLED)
                core = [it for it in plan if it["role"] != "e2adapter"]
                _register(container_spawner.spawn_instances(run_uuid, mode, core, topo))
                health = container_spawner.wait_healthy_instances(instances)
                if not all(health.values()):
                    raise RuntimeError(f"per-run 容器未就緒: {health}")
                e2_items = [it for it in plan if it["role"] == "e2adapter" and it["gnb"] not in defer_nodes]
                if defer_nodes:
                    _DEFERRED[run_uuid] = {"mode": mode, "topo": topo,
                                           "items": [it for it in plan if it["role"] == "e2adapter" and it["gnb"] in defer_nodes]}
                if e2_items:
                    ports = {k: v["host_port"] for k, v in instances.items() if v["role"] == "cu"}
                    _register(container_spawner.spawn_instances(run_uuid, mode, e2_items, topo, cu_host_ports=ports))
                    e2_keys = {it["key"] for it in e2_items}
                    health = container_spawner.wait_healthy_instances({k: v for k, v in instances.items() if k in e2_keys}, timeout_sec=90)
                    if not all(health.values()):
                        raise RuntimeError(f"e2adapter 未就緒: {health}")
                    e2_port = (instances.get(f"e2adapter-{g0.e2_index}") or {}).get("host_port")
                ue_host = instances["ue"]["name"]; cu_host = instances[f"cu-{g0.e2_index}"]["name"]
                # 2026-09-29 O1/SMO:每 gNB 起 facade + 兩顆 o1-adapter(不進 health monitor;失敗不擋 run)
                try:
                    _o1rid = container_spawner.rid_of(run_uuid)
                    _o1scn = str((t.get("scene") or {}).get("legacy_scenario_id") or (t.get("scene") or {}).get("name") or "")
                    _O1_TOPO[run_uuid] = (_o1rid, topo, _o1scn)
                    o1_spawner.spawn(_o1rid, run_uuid, topo, instances, scenario_id=_o1scn)
                except Exception as _o1exc:  # noqa: BLE001
                    logger.warning("O1 spawn skipped: %s", _o1exc)
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
                # 閘道 0.8.4:所有 node E2 Setup 完成(CONNECTED)後啟用,之後才能經閘道下控制(宣告已在開容器前做完)
                if settings.PER_RUN_ENABLED and _ric_gw and not (isinstance(_ric_gw, dict) and _ric_gw.get("error")) and not defer_nodes:
                    import threading as _th
                    _th.Thread(target=platform_clients.ric_activate_when_ready, args=(run_uuid,),
                               name=f"ric-activate-{run_uuid[-8:]}", daemon=True).start()
                # 啟動新的一輪 = 上一輪已經用完 —— 這時候清過期歸檔最安全
                # (跑完就清會讓外部 Agent 來不及 pull;見 archive_retention 的說明)
                from main.apps.run_telemetry_archive.services.optional import archive_retention
                _purged = archive_retention.apply_on_start(run_uuid)
                if _purged:
                    logger.info("run %s 啟動前歸檔清理: %s", run_uuid, _purged)
                if settings.PER_RUN_ENABLED:
                    # 多 gNB:一條歸檔執行緒輪詢每個 gNB 的 CU 與 e2adapter,資料標上 node_id / meid
                    arch_nodes = [{"node_id": g.name, "meid": "" if no_ric else g.meid, "cu_host": g.cu_host,
                                   "e2_port": (instances.get(f"e2adapter-{g.e2_index}") or {}).get("host_port")}
                                  for g in topo.gnbs]
                    du0 = next((v["name"] for k, v in sorted(instances.items()) if v.get("role") == "du"), None)
                    cu_archiver.start_archiver(run_uuid, sim_dt_ms, ric_run=_ric_run, nodes=arch_nodes,
                                               ue_host=instances["ue"]["name"], du_host=du0)
                else:
                    cu_archiver.start_archiver(run_uuid, sim_dt_ms, cu_host=cu_host, e2_port=e2_port, ric_run=_ric_run)   # P2-3:run 期間封存 CU 落地表
            else:
                platform_clients.update_scene_run(run_uuid, status="idle", last_result="failed", notes=str(ue.get("message") or "")[:500])
                return error_response("UE driver refused start", ue, 502)
        except Exception as exc:  # noqa: BLE001
            logger.exception("launch start failed run=%s", run_uuid)
            if settings.PER_RUN_ENABLED:
                health_monitor.stop_monitor(run_uuid)
                if _ric_gw and not (isinstance(_ric_gw, dict) and _ric_gw.get("error")):
                    try:   # 已向閘道宣告卻起不來 → 撤回宣告,不留半套場景在 RIC
                        platform_clients.ric_unregister_scenario(run_uuid)
                    except Exception:  # noqa: BLE001
                        logger.exception("RIC unregister after failed start %s", run_uuid)
                try:
                    container_spawner.teardown(run_uuid)
                except Exception:  # noqa: BLE001
                    logger.exception("teardown after failed start %s", run_uuid)
            SqlDbBusinessService.update_entity(LaunchRequest, UUID_FIELD, getattr(req_row, UUID_FIELD), {"status": "failed", "detail": {"error": str(exc)}})
            try:
                platform_clients.update_scene_run(run_uuid, status="idle", last_result="failed", notes=str(exc)[:500])
            except Exception:  # noqa: BLE001
                pass
            return error_response("launch failed", str(exc), 502)
        logger.info("run %s started (speed %.2fx, sim_dt %d)", run_uuid, speed_x, sim_dt_ms)
        return success_response({"scene_run_uuid": run_uuid, "speed_x": speed_x, "sim_dt_ms": sim_dt_ms, "ue": ue.get("data"), "e2_node_id": e2_node, "gnb_id_hex": gnb_id_hex,
                                 "e2_block": block if settings.PER_RUN_ENABLED else None,
                                 "e2_nodes": ([] if no_ric else [{"nodeId": g.name, "meid": g.meid, "gnb_id_hex": g.gnb_id_hex,
                                                                   "cells": [c.cell_id for d in g.dus for c in d.cells]} for g in topo.gnbs])
                                             if settings.PER_RUN_ENABLED else [], "instances": {r: {k: v for k, v in i.items() if k != "run_instance_uuid"} for r, i in instances.items()}}, "started", 201)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def start_e2adapter(request):
        """body {scene_run_uuid}:起 start 時以 defer_e2_nodes 延後的 e2adapter,等健康後照正常流程 activate。"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        run_uuid = str(payload.get("scene_run_uuid") or "")
        d = _DEFERRED.pop(run_uuid, None)
        if not d:
            return error_response("no deferred e2adapter for this run", run_uuid, 404)
        cu_ports = {}
        for i in platform_clients.list_run_instances(run_uuid):
            if i.get("role") == "cu":
                key = next((k for k, v in container_spawner.names_for(run_uuid).items() if v == i.get("name")), None)
                if key:
                    cu_ports[key] = i.get("host_port")
        spawned = container_spawner.spawn_instances(run_uuid, d["mode"], d["items"], d["topo"], cu_host_ports=cu_ports)
        gnb_meid = {g.name: g.meid for g in d["topo"].gnbs}
        for key, info in spawned.items():
            platform_clients.create_run_instance(run_uuid, info["role"], info["container_id"], info["host_port"],
                                                 name=info["name"], e2_node_id=gnb_meid.get(info.get("gnb") or ""))
        health = container_spawner.wait_healthy_instances(spawned, timeout_sec=90)
        import threading as _th
        _th.Thread(target=platform_clients.ric_activate_when_ready, args=(run_uuid,),
                   name=f"ric-activate-{run_uuid[-8:]}", daemon=True).start()
        return success_response({"spawned": {k: v["name"] for k, v in spawned.items()}, "health": health}, "started", 201)

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
            # 2026-09-23(RIC 第三十三輪 run 46 實測):以前先拆容器、最後才 DELETE 場景,
            # 中間約 30 秒 RIC 仍認為場景 active,xApp 送進來的控制會打到已死的 CU →
            # 對方收到 ControlFailure,看起來像我方拒絕。先 deactivate 讓閘道停止轉發,
            # 再拆容器;DELETE 仍留在最後(它同時清 R-NIB 與 xApp)。
            _rr0 = {}
            try:
                _rr0 = platform_clients._registry("Simulation_run/SceneRunReader/read", {"scene_run_uuid": run_uuid}).get("data") or {}
            except Exception:  # noqa: BLE001
                pass
            _nodes0 = [n for n in (_rr0.get("e2_nodes") or []) if isinstance(n, dict) and n.get("meid")]
            if settings.PER_RUN_ENABLED and (_nodes0 or _rr0.get("e2_node_id") or not _rr0):   # no_ric 的場次沒有 E2 node
                try:
                    platform_clients.ric_deactivate_scenario(run_uuid)
                except Exception as exc:  # noqa: BLE001 — 閘道不在不該擋住收工
                    logger.info("RIC 場景 deactivate 失敗(不影響收工):%s", exc)
            containers = None
            if settings.PER_RUN_ENABLED:
                health_monitor.stop_monitor(run_uuid)
                try:  # 2026-09-29 O1:寫「移除 ME」通知(容器由 teardown 依標籤清掉)
                    _o1 = _O1_TOPO.pop(run_uuid, None)
                    if not _o1:   # 編排服務中途重啟過:從容器 label 重建 topo(2026-09-30)
                        _rid = container_spawner.rid_of(run_uuid); _tp = container_spawner.topology_of(run_uuid)
                        if _tp is not None:
                            _o1 = (_rid, _tp, o1_spawner.scenario_of(_rid))
                    if _o1:
                        o1_spawner.on_stop(_o1[0], _o1[1], scenario_id=(_o1[2] if len(_o1) > 2 else ""),
                                           final=str(payload.get("reason") or "") != "auto_restart")
                except Exception as _o1exc:  # noqa: BLE001
                    logger.warning("O1 stop notice skipped: %s", _o1exc)
                containers = container_spawner.teardown(run_uuid)
                for inst in platform_clients.list_run_instances(run_uuid):
                    platform_clients.update_run_instance(inst["run_instance_uuid"], status="stopped")
            platform_clients.update_scene_run(run_uuid, status="idle", last_result="stopped", stopped_at=now.isoformat())
            ric_note = None
            if settings.PER_RUN_ENABLED:   # 收尾第 4 步:SCTP 已關 → 解除場景 → 清 R-NIB(RIC 場景閘道;沒設就只記 log)
                try:
                    rr = platform_clients._registry("Simulation_run/SceneRunReader/read", {"scene_run_uuid": run_uuid}).get("data") or {}
                    # C15:逐 node 清理。多 gNB 場次以 e2_nodes 為準;舊場次只有單一 e2_node_id
                    nodes = [n for n in (rr.get("e2_nodes") or []) if isinstance(n, dict) and n.get("meid")]
                    if not nodes and rr.get("e2_node_id"):
                        nodes = [{"meid": rr["e2_node_id"], "gnb_id_hex": rr.get("gnb_id_hex") or "",
                                  "plmn_mcc": "208", "plmn_mnc": "95"}]
                    if nodes:
                        for n in nodes:
                            platform_clients.notify_ric_stopped(run_uuid, n["meid"], n.get("gnb_id_hex") or "",
                                                                n.get("plmn_mcc") or "208", n.get("plmn_mnc") or "95")   # 舊 webhook(可選)
                        # RIC 端(2026-09-14):DELETE /v1/scenarios/{id} 一次做「釋放全部 meid 綁定 + 逐 node 清 R-NIB」;放最後(容器已停、SCTP 已斷)。
                        # 只有 DELETE 沒清成(404 / 任一 node cleared:false)才逐 node 補呼 /v1/rnib/clear。
                        ric_note = platform_clients.ric_unregister_scenario(run_uuid)
                        purged = bool(ric_note) and not ric_note.get("error") and bool(ric_note.get("rnibPurge")) and all(x.get("cleared") for x in (ric_note.get("rnibPurge") or []))
                        if not purged:
                            ric_note = {"delete": ric_note, "rnib_clear": {
                                n["meid"]: platform_clients.ric_rnib_clear(n["meid"], n.get("gnb_id_hex") or "",
                                                                          n.get("plmn_mcc") or "208", n.get("plmn_mnc") or "95")
                                for n in nodes}}
                except Exception as exc:  # noqa: BLE001
                    logger.warning("RIC cleanup failed: %s", exc)
            SqlDbBusinessService.update_entity(LaunchRequest, UUID_FIELD, getattr(req_row, UUID_FIELD),
                                               {"status": "stopped", "detail": ue, "launch_request_updated_at": TimestampService.get_current_timestamp()})
        except Exception as exc:  # noqa: BLE001
            logger.exception("launch stop failed run=%s", run_uuid)
            return error_response("stop failed", str(exc), 502)
        return success_response({"scene_run_uuid": run_uuid, "ue": ue.get("data"), "archive": archive_stats, "containers": containers, "ric_notified": ric_note}, "stopped", 200)
