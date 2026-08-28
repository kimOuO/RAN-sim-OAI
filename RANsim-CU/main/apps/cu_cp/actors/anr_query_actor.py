"""ANR / E2 Node Information 查詢端點(RC_E2NODEINFO_QUERY 落地).

M0:CU 端 HTTP 觀測 API,回 E2SM-RC §9.3.38 格式的 neighbourCellRelations,
讓 xApp 拉得到 NRT。之後 M1 才經 E2SM-ANR/adapter 對 RIC。
"""
from __future__ import annotations

import json

from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
from main.apps.cu_cp.services.business.anr_seeder import (
    nr_arfcn_from_ghz,
    seed_from_cells,
)
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)



def _anr_intra_enabled() -> bool:
    """ANR 自動建立功能之部署組態(卷面前置檢查用)。false 時 gNB 不自動寫 NRT。"""
    from main.utils.env_loader import get_bool
    return get_bool("ANR_INTRA_ENABLED", default=True)



def _nrt_capacity(cell_id: str | None = None) -> dict:
    """NRT 容量(卷面 nrtCapacity)。used = 該 cell(或全網)已用關係條目數。

    第3題用它證明「容量非阻斷因素」(與第9題容量修剪互為鑑別);
    第9題超限時 ADD 會被拒(見 anr_control_actor)。
    env `ANR_NRT_CAPACITY`(預設 32)。
    """
    from main.utils.env_loader import get_int
    limit = get_int("ANR_NRT_CAPACITY", 32)
    qs = NrCellRelation.objects.all()
    if cell_id:
        qs = qs.filter(source_cell_id=cell_id)
    return {"limit": limit, "used": qs.count()}


def _relation_to_ie(r: NrCellRelation) -> dict:
    """NrCellRelation → E2SM-RC §9.3.38 neighbourCellRelation IE(+卷面延伸)。"""
    # Case#4 過期關係:給 xApp「年齡」信號(now − created_at 秒)。
    # 過期判定 = relationAgeSec 大 + 該關係累計 HO att=0(perNeighbourRelation)→ REMOVE。
    age_sec = None
    if r.created_at is not None:
        try:
            from django.utils import timezone
            age_sec = max(0.0, (timezone.now() - r.created_at).total_seconds())
        except Exception:
            age_sec = None
    return {
        "sourceCellNcgi": r.source_cell_id,
        "targetCellGlobalId": r.target_cgi,
        "targetPhysicalCellId": r.target_pci,
        "targetArfcn": r.target_arfcn,
        "targetRadioAccessTechnology": r.target_rat,
        # 卷面延伸(管理面視圖)
        "isHoAllowed": r.is_ho_allowed,
        "isRemoveAllowed": r.is_remove_allowed,
        "isXnAllowed": r.is_xn_allowed,
        # §9.3.38 正式
        "xnX2Established": r.xn_x2_established,
        "hoValidated": r.ho_validated,
        "version": r.version,
        "relationAgeSec": age_sec,
        # 旗標(封而不刪)
        "flags": {
            "hoBlocklist": r.ho_blocklist,
            "noRemove": r.no_remove,
            "xnBlocklist": r.xn_blocklist,
        },
    }


class AnrQueryActor:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST", "GET"])
    def node_info(request):
        """RC_E2NODEINFO_QUERY(cellId) → {servingCells, neighbourCellRelations}.

        Body(可選):{cell_id}。給了就只回該 source cell 的關係,否則回全部。
        關係表為空時自動種子(冪等,防禦性)。
        """
        cell_id = None
        if request.body:
            try:
                cell_id = (json.loads(request.body) or {}).get("cell_id")
            except json.JSONDecodeError as e:
                return error_response("invalid JSON", str(e), status=400)

        if not NrCellRelation.objects.exists():
            seed_from_cells()

        from main.apps.cu_cp.services.business.anr_kpm_v10 import _a3_ie

        cells_qs = CellConfig.objects.filter(is_active=True)
        if cell_id:
            cells_qs = cells_qs.filter(cell_id=cell_id)
        serving = [
            {
                "ncgi": c.cell_id,
                "physicalCellId": c.pci,
                "arfcn": nr_arfcn_from_ghz(c.frequency_ghz),
                "radioAccessTechnology": "NR",
                # 2026-08-26:UE 端選網要據此排除 barred(TS 38.304 §5.2.4.1
                # 「UE shall not camp on a barred cell」)。CU 的重建早就排除了,
                # UE 的 IDLE 選網卻沒有 —— 第 3 題深邊緣 fixture 因此被 UE
                # 自己駐到 barred 的 n91 上而崩掉。
                "barred": __import__("main.apps.cu_cp.services.common.fixture_state", fromlist=["is_cell_barred"]).is_cell_barred(c.cell_id, c.is_barred),
                # RIC 第五十六輪 B4 —— 與 KPM 觀測面同一組欄位、同一個來源,
                # 兩邊若各自取值,劇本覆寫時就會出現一面舊一面新。
                **_a3_ie(),
            }
            for c in cells_qs
        ]

        rel_qs = NrCellRelation.objects.all()
        if cell_id:
            rel_qs = rel_qs.filter(source_cell_id=cell_id)
        relations = [_relation_to_ie(r) for r in rel_qs]

        # P0-5(2026-08-11):9.3.38 補全 — 頻率關係 + 關係變更審計
        from main.apps.cu_cp.models.nr_relation_change_event import NrRelationChangeEvent
        from main.apps.cu_cp.services.business.anr_kpm import freq_relations
        change_qs = NrRelationChangeEvent.objects.all()
        if cell_id:
            change_qs = change_qs.filter(source_cell_id=cell_id)
        change_events = [
            {"action": e.action, "sourceCellNcgi": e.source_cell_id,
             "targetCellGlobalId": e.target_cgi,
             "by": e.by, "at": e.at.isoformat(), "detail": e.detail,
             "reason": e.detail if e.action.endswith("_REJECTED") else None}
            for e in change_qs[:100]
        ]

        return success_response({
            "servingCells": serving,
            "anrIntraEnabled": _anr_intra_enabled(),
            "nrtCapacity": _nrt_capacity(cell_id),
            "neighbourCellRelations": relations,
            "frequencyRelations": freq_relations(),
            "relationChangeEvents": change_events,
        }, "ok")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def set_barred(request):
        """設定 cell 的 TS 38.331 cellBarred 旗標。Body: {cell_id, barred}

        barred cell 仍會被量測回報,但 UE 不得駐留(RRC 重建時排除)——
        ANR 情境需要「量得到但不收 UE」的鄰居,否則它會把 UE 吸走、情境瓦解。
        """
        try:
            b = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("invalid JSON", str(e), status=400)
        cid = b.get("cell_id")
        if not cid:
            return error_response("cell_id required", status=400)
        barred = bool(b.get("barred", True))
        n = CellConfig.objects.filter(cell_id=cid).update(is_barred=barred)
        logger.info("cellBarred set: %s → %s (rows=%d)", cid, barred, n)
        return success_response({"cell_id": cid, "barred": barred, "updated": n}, "ok")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def reseed(request):
        """手動(重)種子 NRT + CGI 解析。"""
        stats = seed_from_cells()
        return success_response(stats, "ANR seeded")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def indication(request):
        """ANR indication 一包(給 ran_func 6 producer 拉)—— 卷面全部觀測資料塊。
        Body 可選 {cell_id, window_min}。含 timestamp_ms 給 indication header。
        """
        import time
        from main.apps.cu_cp.models.nr_relation_change_event import NrRelationChangeEvent
        from main.apps.cu_cp.services.business.anr_kpm import (
            freq_relations, ho_kpm, meas_aggregate, rlf_kpm,
        )
        from main.apps.cu_cp.services.business.mro import mro_kpm
        cell_id, window_min = None, 10.0
        if request.body:
            try:
                b = json.loads(request.body) or {}
                cell_id = b.get("cell_id")
                window_min = float(b.get("window_min") or 10.0)
            except (json.JSONDecodeError, ValueError):
                pass
        if not NrCellRelation.objects.exists():
            seed_from_cells()
        cells_qs = CellConfig.objects.filter(is_active=True)
        if cell_id:
            cells_qs = cells_qs.filter(cell_id=cell_id)
        serving = [{"ncgi": c.cell_id, "physicalCellId": c.pci,
                    "arfcn": nr_arfcn_from_ghz(c.frequency_ghz),
                    "radioAccessTechnology": "NR"} for c in cells_qs]
        rel_qs = NrCellRelation.objects.all()
        change_qs = NrRelationChangeEvent.objects.all()
        if cell_id:
            rel_qs = rel_qs.filter(source_cell_id=cell_id)
            change_qs = change_qs.filter(source_cell_id=cell_id)
        # v10 是重組後的格式(見 anr_kpm_v10 檔頭)。ANR_SCHEMA=v10 切換;
        # 預設仍為 v8,讓 RIC 端有遷移窗口 —— 直接切會讓現行 xApp 全部讀不到資料。
        from main.utils.env_loader import get_str as _gs2
        if (_gs2("ANR_SCHEMA", "v8") or "v8").lower() == "v10":
            from main.apps.cu_cp.services.business.anr_kpm_v10 import indication_v10
            return success_response(indication_v10(cell_id, window_min), "ok")

        return success_response({
            "timestamp_ms": int(time.time() * 1000),
            "e2NodeInformation": {
                "servingCells": serving,
                "frequencyRelations": freq_relations(),
                "anrIntraEnabled": _anr_intra_enabled(),
                "nrtCapacity": _nrt_capacity(cell_id),
                "neighbourCellRelations": [_relation_to_ie(r) for r in rel_qs],
                "relationChangeEvents": [
                    {"action": e.action, "targetCellGlobalId": e.target_cgi,
                     "by": e.by, "at": e.at.isoformat(), "detail": e.detail,
                     "reason": e.detail if e.action.endswith("_REJECTED") else None}
                    for e in change_qs[:50]],
            },
            "kpmIndication": ho_kpm(window_min),
            "rlfKpm": rlf_kpm(window_min),
            "mroKpm": mro_kpm(window_min),
            "e2MessageCopyAggregate": meas_aggregate(window_min),
        }, "ok")

    # ── P0-2/3/4(2026-08-11):ANR KPM 查詢層 ─────────────────────

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST", "GET"])
    def indication_v10(request):
        """**永遠**回 v10 格式,不受 ANR_SCHEMA 影響 —— 給 RIC 端做遷移開發用。

        切換是全有全無(wire 上同一時間只送一種格式),但那不該連帶把對方的
        開發也卡住。這支讓 RIC 在我們還送 v8 的期間就能拉到即時的 v10 資料
        做 normalizer 與離線回歸,不必等我們切、也不必靠人工傳檔案。
        Body 可選 {cell_id, window_min}。
        """
        from main.apps.cu_cp.services.business.anr_kpm_v10 import indication_v10 as _v10
        cell_id, window_min = None, 1.0
        if request.body:
            try:
                b = json.loads(request.body) or {}
                cell_id = b.get("cell_id")
                window_min = float(b.get("window_min") or 1.0)
            except (json.JSONDecodeError, ValueError):
                pass
        return success_response(_v10(cell_id, window_min), "ok")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def kpm(request):
        """HO 速率/成功比(cell 級 + perNeighbourRelation)。Body 可選 {window_min}。"""
        from main.apps.cu_cp.services.business.anr_kpm import ho_kpm
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            body = {}
        return success_response(ho_kpm(float(body.get("window_min") or 10.0)), "ok")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def mro_kpm(request):
        """MRO 歸因速率 HO.IntraSys.{TooEarly,TooLate,ToWrongCell}Rate(P2-1)。Body 可選 {window_min}。"""
        from main.apps.cu_cp.services.business.mro import mro_kpm
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            body = {}
        return success_response(mro_kpm(float(body.get("window_min") or 10.0)), "ok")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def rlf_kpm(request):
        """RLF/重建速率 + reestablishmentInboundByPreviousPci(P1-3)。Body 可選 {window_min}。"""
        from main.apps.cu_cp.services.business.anr_kpm import rlf_kpm
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            body = {}
        return success_response(rlf_kpm(float(body.get("window_min") or 10.0)), "ok")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def meas_aggregate(request):
        """量測報告聚合(依 reported PCI 的 RSRP 統計)。Body 可選 {window_min}。"""
        from main.apps.cu_cp.services.business.anr_kpm import meas_aggregate
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            body = {}
        return success_response(meas_aggregate(float(body.get("window_min") or 10.0)), "ok")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def cgi_resolve(request):
        """PCI(+arfcn)→ NCGI 解析(同 PCI 多 cell = confusion)。Body {pci, arfcn?, attempts?}。"""
        from main.apps.cu_cp.services.business.anr_kpm import cgi_resolve
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("invalid JSON", str(e), status=400)
        if body.get("pci") is None:
            return error_response("pci required", status=400)
        return success_response(
            cgi_resolve(int(body["pci"]),
                        int(body["arfcn"]) if body.get("arfcn") is not None else None,
                        int(body.get("attempts") or 3)), "ok")

class AnrFixtureActor:
    """劇本病徵時間軸的啟動入口 —— 讓前端 Start Sim 之後自動佈病。

    在此之前,時間軸得由人手動 `docker exec ... anr_fixture <scenario>` 起,
    等於「劇本會自己跑」只做到一半:節奏是宣告式的,但啟動仍是外部觸發。
    scenario_driver 套用場景後會打這支,CU 自己把時間軸拉起來。

    冪等:時間軸自己有互斥鎖,重複呼叫會被它擋掉(回 already_running)。
    """

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def prepare(request: HttpRequest):
        """起場前準備(round_reset 三機制的 API 化):掃+等靜默驗證、
        pre 區結構與場同生、barred 預埋、殭屍時間軸清理。

        呼叫時機:sim 已停、scene 尚未 apply(scenario_driver Step 1b.5)。
        同步阻塞最長 ~5 分鐘(靜默驗證),呼叫端 timeout 要給足。
        fail-loud:任何一段失敗都在 errors 列出,不靜默(Q11 三層吞錯教訓)。
        """
        import json as _j
        try:
            body = _j.loads(request.body or b"{}")
        except ValueError:
            body = {}
        sid = (body.get("scenario_id") or "").strip()
        if not sid:
            return error_response("scenario_id required", http_status=400)
        from main.apps.cu_cp.services.business.fixture_prepare import prepare
        try:
            out = prepare(sid)
        except FileNotFoundError as exc:
            return error_response("scenario not found", str(exc), http_status=404)
        return success_response(out, "prepared" if not out["errors"] else "prepared_with_errors")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def start(request: HttpRequest):
        import json as _j
        import os
        import subprocess
        try:
            body = _j.loads(request.body or b"{}")
        except ValueError:
            body = {}
        sid = (body.get("scenario_id") or "").strip()
        if not sid:
            return error_response("scenario_id required", http_status=400)

        # 沒有 anr_fixture 區塊的劇本直接回報,不要留下誤導的「已啟動」
        from main.apps.cu_cp.management.commands.anr_fixture import _load_steps
        try:
            steps = _load_steps(sid)
        except FileNotFoundError as exc:
            return error_response("scenario not found", str(exc), http_status=404)
        if not steps:
            return success_response({"scenario_id": sid, "started": False,
                                     "reason": "no anr_fixture block"}, "ok")
        try:
            # 記錄現行劇本 —— 場景切換時 CU 會重啟,每個 worker 的續跑都會把
            # 「上一個劇本」的時間軸孵回來,跟新劇本的接管互相殘殺
            # (2026-08-27 實測:stale_pci 的殭屍續跑反過來殺掉 xn_discovery 的新實例)。
            # 非現行 sid 的實例看到這個檔就自行退場。
            with open("/app/tmp/anr_fixture.current", "w") as f:
                f.write(sid)
            subprocess.Popen(
                ["python", "/app/manage.py", "anr_fixture", sid],
                stdout=open(f"/app/tmp/fixture_{sid}.log", "a"),
                stderr=subprocess.STDOUT, start_new_session=True, env={**os.environ})
        except OSError as exc:
            return error_response("spawn failed", str(exc), http_status=500)
        logger.warning("[fixture] 場景啟動觸發時間軸:%s(%d 步)", sid, len(steps))
        return success_response({"scenario_id": sid, "started": True,
                                 "steps": len(steps)}, "ok")
