"""外部 Agent 介面 I-3 —— 觸發情境。

對方以「場域 + 負載型態 + 長度 + 種子 + 事件清單」啟動一次模擬,並把這份請求
原樣存成該次任務的正確答案。所以這支的責任不只是「把模擬跑起來」,而是:

  1. 凡是我方做不到的,**啟動前就明確退回**,不可默默忽略 ——
     對方存了一份「第 360 秒關掉 C02」的答案,我方沒關,整個題目的答案就是錯的。
  2. 實際採用的參數要 echo 回去(含預設值填充後的結果),對方據此校正它的存檔。
  3. 事件以劇本時鐘觸發,並落 RunControlEvent 供 I-7 核對。

與我方既有啟動流程的關係:這支不另造一條啟動路徑,而是設好旋鈕後呼叫既有的
LaunchController/start。啟動邏輯只有一份,前端與 Agent 走的是同一條。
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.agent_api.services.optional import e2_identity, event_scheduler, scenario_events
from main.apps.agent_api.services.optional.field_config import _cells_of, _cfg_version
from main.apps.run_lifecycle.services.optional import container_spawner, platform_clients
from main.apps.run_telemetry_archive.services.optional import cu_archiver
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)

# 自己打自己的啟動介面。不直接 import LaunchController —— 那支是同步長流程
# (起容器、等健康、送 E2 Setup),走 HTTP 與前端完全同路徑,行為一致。
_LAUNCH_URL = "http://127.0.0.1:8000/api/v0.1/Run_orchestrator/Run_lifecycle/LaunchController/start"


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


def _instance_id(payload: dict) -> str:
    """對同一組參數的決定性識別(規格建議欄位 instance_id)。

    對方用它判斷「這組參數我是不是已經跑過了」。所以只取影響模擬結果的欄位,
    不含 requester_task_id 這種純追溯用的。
    """
    core = {
        "field_id": payload.get("field_id"),
        "load_profile": payload.get("load_profile"),
        "ue_count": payload.get("ue_count"),
        "duration_s": payload.get("duration_s"),
        "seed": payload.get("seed"),
        "magnitude": payload.get("magnitude"),
        "events": payload.get("events") or [],
    }
    blob = json.dumps(core, sort_keys=True, ensure_ascii=False, default=str)
    return "SC-" + hashlib.sha1(blob.encode()).hexdigest()[:10]


def _pick_run(scene_uuid: str) -> dict | None:
    """場域(scene)→ 可啟動的 scene_run。

    一個場域通常只有一個 run 設定(通道快取是綁著它預算的)。有多個時取最近更新的;
    正在跑的優先退回,由呼叫端判斷要不要擋。
    """
    rows = (platform_clients.list_scene_runs() or {}).get("data") or []
    mine = [r for r in rows if str(r.get("f_scene_uuid")) == scene_uuid]
    if not mine:
        return None
    mine.sort(key=lambda r: str(r.get("scene_run_updated_at") or ""), reverse=True)
    return mine[0]


class ScenarioController:
    """Component name in URL: ScenarioController"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def run(request):  # noqa: C901 — 驗證分支多,拆開反而更難讀
        """I-3 觸發情境。body 見需求規格 I-3。"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)

        field_id = str(payload.get("field_id") or "").strip()
        if not field_id:
            return error_response("Validation failed", {"field_id": "required"}, 400)
        if payload.get("duration_s") is None:
            return error_response("Validation failed", {"duration_s": "required"}, 400)
        if payload.get("seed") is None:
            return error_response("Validation failed",
                                  {"seed": "required(決定性:同參數同 seed 須得相同資料)"}, 400)

        # ── 場域與配置版本 ────────────────────────────────────────
        try:
            tree = (platform_clients.read_scene_tree(field_id) or {}).get("data") or {}
        except Exception as exc:  # noqa: BLE001
            return error_response("registry unreachable", str(exc), 502)
        scene = tree.get("scene") or {}
        if not scene:
            return error_response("field not found", field_id, 404)

        want_ver = payload.get("config_version")
        have_ver = _cfg_version(tree)
        if want_ver is not None and str(want_ver) != str(have_ver):
            # 規格明定不符時回錯 —— 對方拿舊配置算出來的答案會對不上新場域
            return error_response(
                "config_version mismatch",
                {"requested": str(want_ver), "current": str(have_ver),
                 "hint": "請重新以 I-2 取得配置後再觸發"}, 409)

        run_row = _pick_run(field_id)
        if not run_row:
            return error_response(
                "field has no runnable configuration",
                {"field_id": field_id,
                 "hint": "該場域尚未建立 run 設定(通道快取須先預算)"}, 409)
        run_uuid = str(run_row["scene_run_uuid"])
        mode = str(run_row.get("mode") or "cached")

        if str(run_row.get("status") or "") in ("running", "starting", "precomputing"):
            return error_response(
                "field is already running",
                {"run_id": run_uuid, "status": run_row.get("status"),
                 "hint": "同一場域同時只能跑一場(E2 識別要固定給 xApp)"}, 409)
        if mode == "cached" and not run_row.get("cache_path"):
            return error_response(
                "channel cache not ready",
                {"run_id": run_uuid, "hint": "該場域尚未完成通道預算"}, 409)

        # ── 長度 ──────────────────────────────────────────────────
        duration_s = int(payload["duration_s"])
        max_dur = int(run_row.get("duration_sec") or 0)
        if max_dur and duration_s > max_dur:
            # 快取只有這麼長,跑不過去。給實際上限而不是硬截斷 —— 對方要知道拿到的窗數會變少
            return error_response(
                "duration_s exceeds field capacity",
                {"requested": duration_s, "max_duration_s": max_dur,
                 "hint": "通道快取的長度即為上限;需要更長須另行預算"}, 400)

        # ── 負載型態與人數 ────────────────────────────────────────
        notes: list[str] = []
        ues = tree.get("ues") or []
        want_profile = payload.get("load_profile")
        have_profile = str(scene.get("name") or "")
        if want_profile and str(want_profile) != have_profile:
            return error_response(
                "unknown load_profile",
                {"requested": want_profile, "available": [have_profile],
                 "hint": "本場域的人流為寫定資料,型態名即場域名(見 I-1)"}, 400)
        if payload.get("ue_count") is not None and int(payload["ue_count"]) != len(ues):
            # 不是錯誤,但要講清楚實際用的是幾人 —— 靜默忽略會讓對方以為改成功了
            notes.append(
                f"ue_count={payload['ue_count']} 未採用:本場域人流為寫定路徑,"
                f"實際 {len(ues)} 人(見 I-1 的 load_profiles[].note)")

        # ── 事件 ──────────────────────────────────────────────────
        pairs = _cells_of(tree)
        cell_ids = [str(c.get("name") or "") for _g, c in pairs]
        inactive = [str(c.get("name") or "") for _g, c in pairs
                    if c.get("is_active") is False]
        # 執行期的 cell_id 帶 E2 槽位標籤(e03:src),但對方從 I-2 拿到的是 src / ncgi。
        # 標籤由場域釘住的 e2_slot 決定 —— 釘住才推得出來,這也是 I-1 只把釘住的場域
        # 標為可用的原因。沒釘就退回執行期識別無法事先決定。
        slot = scene.get("e2_slot")
        if not slot:
            return error_response(
                "field has no pinned E2 slot",
                {"field_id": field_id,
                 "hint": "場域未釘 e2_slot,cell 識別要啟動後才確定,無法事先注入事件"}, 409)
        ident = e2_identity.field_e2_identity(int(slot), cell_ids)
        name_to_runtime = {c["name"]: c["cell_id"] for c in ident["cells"]}
        ncgi_to_name = {c["ncgi"]: c["name"] for c in ident["cells"] if c.get("ncgi")}
        events, errs = scenario_events.validate(
            payload.get("events") or [],
            cell_ids=cell_ids, inactive_cell_ids=inactive,
            duration_s=duration_s, mode=mode,
            name_to_runtime=name_to_runtime, ncgi_to_name=ncgi_to_name)
        if errs:
            # 一筆都不放行。半套執行 = 給對方錯的正確答案
            return error_response(
                "event validation failed",
                {"errors": errs,
                 "supported_types": scenario_events.supported_types(cell_ids, inactive, mode),
                 "cells": cell_ids}, 400)
        scheduled = scenario_events.expand_with_revert(events)

        # ── 決定性:run seed 下到 DU 的 slot 引擎 ──────────────────
        seed = int(payload["seed"])
        try:
            platform_clients.set_run_knob(run_uuid, "run_seed", str(seed))
        except Exception as exc:  # noqa: BLE001
            return error_response("failed to set run seed", str(exc), 502)

        # ── 啟動 ──────────────────────────────────────────────────
        speed_x = float(run_row.get("speed_x") or 1.0)
        started_at = timezone.now()
        try:
            req = urllib.request.Request(
                _LAUNCH_URL,
                data=json.dumps({"scene_run_uuid": run_uuid, "mode": mode,
                                 "speed_x": speed_x}).encode(),
                headers={"content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as resp:
                launch = json.loads(resp.read().decode() or "{}") or {}
        except Exception as exc:  # noqa: BLE001
            logger.exception("I-3 啟動失敗 run=%s", run_uuid)
            return error_response("launch failed", str(exc), 502)
        if not launch.get("success"):
            return error_response("launch failed", launch.get("message") or launch, 502)

        # ── 事件排程 ──────────────────────────────────────────────
        n_sched = 0
        hosts = container_spawner.names_for(run_uuid)
        try:
            # deadline 一律給 —— 沒有事件的類型一也要在 duration_s 收工,
            # 否則會一路跑到劇本自身的長度(走廊劇本是 8 小時)。
            n_sched = event_scheduler.start(
                run_uuid, scheduled, hosts,
                run_seq=cu_archiver.active_run_seq(run_uuid),
                deadline_s=float(duration_s))
        except Exception as exc:  # noqa: BLE001
            logger.exception("事件排程失敗 run=%s", run_uuid)
            return error_response(
                "simulation started but event scheduling failed",
                {"run_id": run_uuid, "error": str(exc),
                 "hint": "請以 I-4 確認後停止該 run 並重試"}, 500)

        eta = started_at + timedelta(seconds=duration_s / max(speed_x, 1e-6))
        return success_response({
            "run_id": run_uuid,
            "instance_id": _instance_id(payload),
            "status": "running",
            "started_at": started_at.isoformat(),
            "estimated_finish_at": eta.isoformat(),
            "echo": {
                "field_id": field_id,
                "config_version": str(have_ver),
                "load_profile": have_profile,
                "ue_count": len(ues),
                "duration_s": duration_s,
                "seed": seed,
                "magnitude": float(payload.get("magnitude") or 1.0),
                "mode": mode,
                "speed_x": speed_x,
                "events": len(events),
                "events_scheduled": n_sched,     # 含自動補的還原動作
                "requester_task_id": payload.get("requester_task_id"),
            },
            # magnitude 我方沒有對應的調節維度 —— 收下但不作用,必須講明
            "unavailable_fields": ["magnitude(我方事件無強度維度,收下但不作用)"],
            "notes": notes,
        }, "scenario started", 200)
