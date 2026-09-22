"""外部 Agent 介面 I-4 — 查詢執行狀態。

對方觸發模擬(I-3)後輪詢這支,直到完成才去取觀測資料(I-5/I-6)。
關鍵是 `status` 要分得出「跑完了」與「中途停掉/失敗」—— 前者可以取資料,
後者要重跑。我方內部狀態值與規格不同,在這裡對映。
"""
from __future__ import annotations

import json

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.run_lifecycle.services.optional import platform_clients
from main.apps.agent_api.services.optional import config_changes, event_scheduler, run_events
from main.apps.agent_api.services.optional.e2_identity import TAG_SEP
from main.apps.run_telemetry_archive.models.run_handover_event import RunHandoverEvent
from main.apps.run_telemetry_archive.models.run_control_event import RunControlEvent
from main.apps.run_telemetry_archive.models.run_kpm_sample import RunKpmSample
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)

# 我方 status → 規格的三值。draft/ready/pending 都還沒跑,對方看到的是 running 之前的狀態,
# 這裡一律回 running 會誤導,所以多給一個 pending(規格沒定義,但比謊報好)。
_STATUS_MAP = {
    "running": "running",
    "starting": "running",
    "precomputing": "running",
    "done": "done",
    "stopped": "failed",      # 人為中止:對方不該當成正常完成去取資料
    "failed": "failed",
    "draft": "pending",
    "ready": "pending",
    "pending": "pending",
}


def _body(request) -> dict:
    return json.loads(request.body or b"{}")


def _ue_names(run_id: str) -> list[str] | None:
    """該 run 實際跑的 UE 名單 —— 問 UE 容器,拿不到回 None(不是空陣列)。

    空陣列會被讀成「沒有 UE」,與「我方查不到」是兩回事。
    """
    import urllib.request

    from main.apps.run_lifecycle.services.optional import container_spawner
    try:
        name = container_spawner.names_for(run_id)["ue"]
        req = urllib.request.Request(
            f"http://{name}:8000/api/v0.1/UE/Scenario/ScenarioController/status",
            data=b"{}", headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            d = (json.loads(resp.read().decode() or "{}") or {}).get("data") or {}
        return d.get("ue_names")
    except Exception:  # noqa: BLE001 — run 已停或容器不在,不該讓狀態查詢失敗
        return None


class RunReader:
    """Component name in URL: RunReader"""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def status(request):
        """body {run_id} —— run_id 即我方的 scene_run_uuid。"""
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        run_id = str(payload.get("run_id") or payload.get("scene_run_uuid") or "").strip()
        if not run_id:
            return error_response("Validation failed", {"run_id": "required"}, 400)

        try:
            res = platform_clients.read_scene_run(run_id)
        except Exception as exc:  # noqa: BLE001
            return error_response("registry unreachable", str(exc), 502)
        rows = res.get("data") if res.get("success") else None
        row = (rows[0] if isinstance(rows, list) else rows) if rows else None
        if not row:
            return error_response("run not found", run_id, 404)

        raw = str(row.get("status") or "")
        # 對方經 I-3 指定的長度(旋鈕);沒有就是走前端啟動的 run,回劇本自身長度
        try:
            _kn = {r.get("key"): r.get("value") for r in platform_clients.read_run_knobs(run_id)}
            agent_dur = int(float(_kn["agent_duration_s"])) if _kn.get("agent_duration_s") else None
        except Exception:  # noqa: BLE001
            agent_dur = None
        # 封存筆數 = 對方可取回的窗數。只算最後一次 run_seq —— 同一個 scene_run 重跑過
        # 的話舊資料還在表裡,全部加起來會讓對方以為有更多窗可取。
        try:
            seqs = RunKpmSample.objects.filter(f_scene_run_uuid=run_id).order_by("-run_seq").values_list("run_seq", flat=True)[:1]
            windows = RunKpmSample.objects.filter(f_scene_run_uuid=run_id, run_seq=seqs[0]).count() if seqs else 0
        except Exception:  # noqa: BLE001
            windows = None

        # notes 是累積的自由文字,上一輪的訊息會留著。只有本輪真的失敗才拿它當 error,
        # 否則會把「上次跑完」的註記當成這次的失敗原因回給對方(實測踩過)。
        notes = str(row.get("notes") or "")
        mapped = _STATUS_MAP.get(raw, "running")
        err = notes if (mapped == "failed" and raw == "failed" and notes) else None
        if mapped == "failed" and raw == "stopped":
            err = "run 由人為或外部中止(非跑完);資料可能不完整"
        return success_response({
            "run_id": run_id,
            "status": _STATUS_MAP.get(raw, "running"),
            "native_status": raw,          # 我方原始值,除錯用
            "progress_s": row.get("progress_sec"),
            "duration_s": agent_dur if agent_dur is not None else row.get("duration_sec"),
            "started_at": row.get("started_at"),
            "finished_at": row.get("stopped_at"),
            "windows_available": windows,
            # I-3 注入的事件進度 —— 對方輪詢時要知道事件是不是都觸發了。
            # 沒排事件(類型一)或 orchestrator 重啟後失去排程器時為 null。
            "events": event_scheduler.status(run_id),
            # I-3 若以 ue_count 取子集,這裡給實際採用的名單(對照 I-2 的 ues)
            "ue_names": (_names := _ue_names(run_id)),
            "error": err,
            "unavailable_fields": ([] if windows is not None else ["windows_available"])
                                  + ([] if _names is not None else
                                     ["ue_names(run 已停,UE 容器不在;啟動時的名單見 I-3 回應的 echo.ue_names)"]),
        }, "ok", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def config_changes(request):
        """I-7 組態變更紀錄。body {run_id, from?, to?, origin?}

        from/to 是自模擬起點的偏移秒數;origin 可篩 triggered_event / son_function / system。
        """
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        run_id = str(payload.get("run_id") or payload.get("scene_run_uuid") or "").strip()
        if not run_id:
            return error_response("Validation failed", {"run_id": "required"}, 400)

        qs = RunControlEvent.objects.filter(f_scene_run_uuid=run_id)
        # 同一個 scene_run 重跑過的話舊資料還在;只給最後一輪,否則對方會看到不屬於這次的變更
        seqs = list(qs.order_by("-run_seq").values_list("run_seq", flat=True)[:1])
        if seqs:
            qs = qs.filter(run_seq=seqs[0])
        if payload.get("from") is not None:
            qs = qs.filter(at_sim_ms__gte=int(float(payload["from"]) * 1000))
        if payload.get("to") is not None:
            qs = qs.filter(at_sim_ms__lte=int(float(payload["to"]) * 1000))

        rows = list(qs.order_by("at_sim_ms", "id").values(
            "at_sim_ms", "source", "action_type", "target", "outcome", "detail",
            "run_control_event_created_at"))
        for r in rows:
            if r.get("run_control_event_created_at") is not None:
                r["run_control_event_created_at"] = r["run_control_event_created_at"].isoformat()
        changes = [config_changes.to_change(r) for r in rows]
        want = payload.get("origin")
        if want:
            changes = [c for c in changes if c["origin"] == want]

        n_son = sum(1 for c in changes if c["origin"] == "son_function")
        return success_response({
            "run_id": run_id, "changes": changes, "count": len(changes),
            # 主動點名自主行為的筆數 —— 對方最需要知道的就是「我方自己動了幾次」
            "son_function_count": n_son,
            "unavailable_fields": sorted({f for c in changes for f in c["unavailable_fields"]}),
        }, "ok", 200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def events(request):
        """I-6 事件紀錄。body {run_id, from?, to?, types?}

        from/to 是自模擬起點的偏移秒數;types 可篩型別(見 run_events.ALL_TYPES)。
        cell 識別一律剝掉執行期的槽位前綴("e03:src" → "src"),與 I-2 宣告的一致。
        """
        try:
            payload = _body(request)
        except json.JSONDecodeError as exc:
            return error_response("Invalid JSON", str(exc), 400)
        run_id = str(payload.get("run_id") or payload.get("scene_run_uuid") or "").strip()
        if not run_id:
            return error_response("Validation failed", {"run_id": "required"}, 400)
        want = set(payload.get("types") or run_events.ALL_TYPES)
        t0 = payload.get("from")
        t1 = payload.get("to")

        def _strip(cid: str) -> str:
            return cid.split(TAG_SEP, 1)[1] if cid and TAG_SEP in cid else cid

        # gNB 歸屬:執行期的 cell 沒有帶 gnb_id,匯出時回查 registry 還原分組
        gnb_of_cell: dict[str, str] = {}
        pci_of_cell: dict[str, int] = {}
        try:
            tree = (platform_clients.read_scene_tree_by_run(run_id) or {}).get("data") or {}
            for g in tree.get("gnbs") or []:
                for du in g.get("dus") or []:
                    for c in du.get("cells") or []:
                        gnb_of_cell[str(c.get("name") or "")] = str(g.get("name") or "")
                        if c.get("pci") is not None:
                            pci_of_cell[str(c.get("name") or "")] = int(c["pci"])
        except Exception:  # noqa: BLE001 — 查不到就讓 gnb_id 留空,不擋整支
            logger.info("gNB 歸屬回查失敗:%s", run_id)

        def _seq_filter(qs):
            """同一個 scene_run 重跑過的話舊資料還在,只給最後一輪。"""
            seqs = list(qs.order_by("-run_seq").values_list("run_seq", flat=True)[:1])
            return qs.filter(run_seq=seqs[0]) if seqs else qs

        out: list[dict] = []
        # 牆鐘對照永遠要建(不管有沒有要 meas_report):所有事件的 ts / ts_iso 都靠它
        q_kpm = _seq_filter(RunKpmSample.objects.filter(f_scene_run_uuid=run_id))
        to_wall = run_events.wall_clock_mapper(
            list(q_kpm.order_by("window_index").values("sim_time_ms", "wall_time_ms")))
        if want & {run_events.MEAS_REPORT}:
            rows = list(q_kpm.order_by("window_index").values("sim_time_ms", "per_ue"))
            out += run_events.meas_reports(rows, gnb_of_cell, _strip)
        if want & {run_events.HO_EXE_SUCC, run_events.HO_EXE_FAIL, run_events.HO_PREP_FAIL,
                   run_events.RLF, run_events.RRC_REESTAB_REQ}:
            q = _seq_filter(RunHandoverEvent.objects.filter(f_scene_run_uuid=run_id))
            rows = list(q.order_by("at_sim_ms", "id").values(
                "at_sim_ms", "ue_id", "source_cell", "target_cell", "outcome", "detail"))
            out += run_events.handover_events(rows, gnb_of_cell, _strip, pci_of_cell)
        if want & {run_events.CGI_RESOLUTION}:
            q = _seq_filter(RunControlEvent.objects.filter(f_scene_run_uuid=run_id))
            rows = list(q.order_by("at_sim_ms", "id").values(
                "at_sim_ms", "action_type", "target", "detail"))
            out += run_events.cgi_resolutions(rows, gnb_of_cell, _strip)

        out = [e for e in out if e["type"] in want]
        if t0 is not None:
            out = [e for e in out if e["offset_s"] >= float(t0)]
        if t1 is not None:
            out = [e for e in out if e["offset_s"] <= float(t1)]
        out.sort(key=lambda e: (e["offset_s"], e["type"]))
        for e in out:
            e["ts"], e["ts_iso"] = to_wall(e["offset_s"])
        no_wall = bool(out) and out[0]["ts"] is None

        counts: dict[str, int] = {}
        for e in out:
            counts[e["type"]] = counts.get(e["type"], 0) + 1
        return success_response({
            "run_id": run_id, "events": out, "count": len(out), "by_type": counts,
            # 我方量測是週期性的,不是 A3 事件觸發 —— 明講而不是讓對方誤會
            "notes": [
                # A3 我方有做(TS 38.331 §5.5.4.4:offset/hysteresis/TTT/L3 濾波 k=4),
                # 差別在「誰決定送報告」:真實 UE 自己判 A3、條件成立才送;我方 DU 每個
                # PM 視窗都送,A3 在 CU 端評估。A3 是否觸發看 ho_exe_* 的 payload.trigger。
                "meas_report 為週期性回報(每個 PM 視窗一次);A3 判斷在 CU 端執行,"
                "觸發結果見 ho_exe_succ / ho_exe_fail 的 payload.trigger(A3_TTT)",
                "rrc_reestab_req 由 RLF 事件導出,無獨立訊息紀錄(時間與對應的 rlf 相同)",
            ],
            "unavailable_fields": (["events[].ts / ts_iso(這一輪尚無 KPM 視窗可對照牆鐘)"] if no_wall else []) + ["events[].payload.last_rsrp(RLF 當下只留 SINR)",
                                   "conn_release(無此事件)"],
        }, "ok", 200)
