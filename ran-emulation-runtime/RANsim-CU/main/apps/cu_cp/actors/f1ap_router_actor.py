"""F1AP CU-side router. Mirrors OAI's F1AP_CU_task switch dispatch.

OAI ref: openair2/F1AP/f1ap_cu_task.c (F1AP_CU_task at L110-239).
"""
from __future__ import annotations

import hashlib
import json

from django.db import transaction
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.cell_measurement_log import CellMeasurementLog
from main.apps.cu_cp.models.du_registry import DuRegistry
from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.models.measurement_log import MeasurementLog
from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.serializers.f1ap_serializers import (
    F1SetupWriteSerializer,
    MeasurementReportWriteSerializer,
    UlRrcMessageWriteSerializer,
)
from main.apps.cu_cp.services.business.cuup_client_operations import CuupClientBusinessService
from main.apps.cu_cp.services.business.du_client_operations import DuClientBusinessService
from main.apps.cu_cp.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.apps.cu_cp.services.common.uuid_service import UUIDService
from main.apps.cu_cp.services.optional.f1ap.f1ap_handler import F1apHandler
from main.apps.cu_cp.services.optional.mobility.a3_handover_calculation import (
    A3HandoverCalculation, get_ue_state,
)
from main.apps.cu_cp.services.optional.ngap.ngap_handler import NgapHandler
from main.utils.env_loader import default_served_plmn, get_bool, get_str
from main.apps.cu_cp.services.optional.rrc.message_handler import (
    RrcMessageHandler, RrcMessageType,
)
from main.apps.cu_cp.services.optional.rrc.state_machine import RrcStateMachine
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


def _bump_estab_counter(cell_id: str, *, att: int = 0, succ: int = 0) -> None:
    """2026-08-12:per-cell RRC 建立真累計(只加不減;HO 不經此路徑,語意正確)。"""
    if not cell_id:
        return
    try:
        from django.db.models import F
        from main.apps.cu_cp.models.rrc_estab_counter import RrcEstabCounter
        obj, created = RrcEstabCounter.objects.get_or_create(
            cell_id=cell_id, defaults={"att": att, "succ": succ,
                                       "updated_at": TimestampService.now()})
        if not created:
            RrcEstabCounter.objects.filter(cell_id=cell_id).update(
                att=F("att") + att, succ=F("succ") + succ,
                updated_at=TimestampService.now())
    except Exception:
        logger.exception("bump estab counter failed for %s", cell_id)


def _refresh_neighbours() -> None:
    """cell 有變:交易提交後再對鄰居 gNB 重做 Xn Setup(帶最新的 served cells)。"""
    try:
        from main.apps.cu_cp.services.business import xn
        transaction.on_commit(xn.ensure_xn_setup)
    except Exception:  # noqa: BLE001 — Xn 更新失敗不擋 F1
        logger.exception("Xn served-cell update scheduling failed")


def _resolve_ue_base(ue_id: str) -> int:
    """UE 的 base id(rrc_ue_id = ran_ue_ngap_id = base，amf_ue_ngap_id = base + 1）。

    三種模式(env 控制),讓 amf/f1ap 能對齊 xApp 表上「🔒固定」的值:
      1. UE_ID_FIXED_MAP 有列此 ue_id → 用指定固定值。
         格式 "ue_id:base,ue_id:base"，例 "cco_ue_01:1056001737"(→ amf 1056001738)。
      2. UE_ID_RANDOM=1 → Python hash(per-process 隨機、非決定性，舊行為，測試用)。
      3. 預設 → SHA-1(ue_id)(跨重啟決定性穩定，與 cell nr_cellid 同套路)。
    """
    fixed_map = get_str("UE_ID_FIXED_MAP", "cco_ue_01:1056001737") or ""
    for pair in fixed_map.split(","):
        name, sep, val = pair.partition(":")
        if sep and name.strip() == ue_id:
            try:
                return int(val.strip()) % (2 ** 31)
            except ValueError:
                break
    if get_bool("UE_ID_RANDOM", False):
        return abs(hash(ue_id)) % (2 ** 31)
    return int.from_bytes(hashlib.sha1(ue_id.encode("utf-8")).digest()[:4], "big") % (2 ** 31)


class F1ApRouterActor:
    """All F1-C messages from DU come through this Actor."""

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def du_setup(request: HttpRequest):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)

        serializer = F1SetupWriteSerializer(data=body)
        if not serializer.is_valid():
            return error_response("validation failed", serializer.errors, status=400)

        data = serializer.validated_data
        gnb_du_id = data["gnb_du_id"]
        cells = data["served_cells"]

        now = TimestampService.now()
        du_uuid = UUIDService.generate_uuid("du", gnb_du_id)

        SqlDbBusinessService.upsert_entity(
            DuRegistry,
            "gnb_du_id",
            gnb_du_id,
            defaults={
                "du_uuid": du_uuid,
                "name": data.get("du_name") or f"DU#{gnb_du_id}",
                "endpoint": (data.get("du_endpoint") or "").rstrip("/"),
                "served_cells_json": cells,
                "registered_at": now,
                "last_seen_at": now,
            },
        )

        incoming_cell_ids = [c["cell_id"] for c in cells]
        for cell in cells:
            cell_uuid = UUIDService.generate_uuid("cell", cell["cell_id"])
            SqlDbBusinessService.upsert_entity(
                CellConfig,
                "cell_id",
                cell["cell_id"],
                defaults={
                    "cell_uuid": cell_uuid,
                    "pci": cell["pci"],
                    "frequency_ghz": cell["frequency_ghz"],
                    "bandwidth_mhz": cell["bandwidth_mhz"],
                    "served_plmn": cell.get("served_plmn") or default_served_plmn(),
                    "gnb_id": cell.get("gnb_id", ""),
                    "served_by_du_id": gnb_du_id,
                    # P2.1: OAI 真實 nr_cellid 從 F1 Setup 帶上來;沒帶就留 None → SHA-1 hash fallback
                    "nr_cellid": cell.get("nr_cellid"),
                    # 2026-09-22: PEE.AvgPower / PEE.Energy 的輸入
                    "tx_power_dbm": cell.get("tx_power_dbm"),
                    "created_at": now,
                    "updated_at": now,
                },
            )

        # 把屬於這個 DU 但不在這次 F1Setup 的 cell 刪掉（DU 重啟 → 重發 F1Setup 表示
        # 「我現在 serve 的就是這些」，不在的就應該移除）。只限 same gnb_du_id，避免動到其他 DU 的 cells。
        stale = CellConfig.objects.filter(served_by_du_id=gnb_du_id).exclude(cell_id__in=incoming_cell_ids)
        deleted = stale.count()
        if deleted > 0:
            stale.delete()
            logger.info("F1 Setup cleared %d stale cells from DU#%s", deleted, gnb_du_id)

        logger.info("F1 Setup accepted: DU#%s (%s) with %d cell(s)", gnb_du_id,
                    data.get("du_endpoint") or "env HTTP_DU_HOST", len(cells))

        # E2SM-ANR M0：cell 就緒後(重)建 intra-gNB 鄰區關係 + CGI 解析(冪等)。
        try:
            from main.apps.cu_cp.services.business.anr_seeder import seed_from_cells
            seed_from_cells()
        except Exception:  # noqa: BLE001 — 種子失敗不應擋 F1 Setup
            logger.exception("ANR seed on F1 Setup failed")

        # 多 gNB:本 gNB 的 served cells 變了 → 重新對鄰居做 Xn Setup(= NG-RAN node Configuration Update)
        _refresh_neighbours()

        resp = F1apHandler.build_f1_setup_response(transaction_id=gnb_du_id, accepted=True)
        return success_response(resp, "F1 Setup accepted", status=200)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def du_configuration_update(request: HttpRequest):
        """處理 gNB-DU Configuration Update（3GPP TS 38.473 §8.2.4）。

        DU 在 F1 ACTIVE 後新增 / 修改 / 刪除 cell 會送這個訊息。
        body: {gnb_du_id, transaction_id, served_cells_to_add[], served_cells_to_modify[], served_cells_to_delete[]}
        每個 cell 帶完整 CellConfig 欄位（含 gnb_id、is_active）。
        """
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)

        gnb_du_id = body.get("gnb_du_id")
        if gnb_du_id is None:
            return error_response("gnb_du_id required", status=400)

        to_add = body.get("served_cells_to_add") or []
        to_modify = body.get("served_cells_to_modify") or []
        to_delete = body.get("served_cells_to_delete") or []

        now = TimestampService.now()

        for cell in list(to_add) + list(to_modify):
            if not isinstance(cell, dict):
                continue
            cell_uuid = UUIDService.generate_uuid("cell", cell["cell_id"])
            SqlDbBusinessService.upsert_entity(
                CellConfig,
                "cell_id",
                cell["cell_id"],
                defaults={
                    "cell_uuid": cell_uuid,
                    "pci": cell["pci"],
                    "frequency_ghz": cell["frequency_ghz"],
                    "bandwidth_mhz": cell["bandwidth_mhz"],
                    "served_plmn": cell.get("served_plmn") or default_served_plmn(),
                    "gnb_id": cell.get("gnb_id", ""),
                    "is_active": cell.get("is_active", True),
                    "tx_power_dbm": cell.get("tx_power_dbm"),
                    # 多 gNB:3GPP NCI(gNB ID ‖ 本地 cell ID)隨 Configuration Update 帶上來
                    "nr_cellid": cell.get("nr_cellid"),
                    "served_by_du_id": gnb_du_id,
                    "created_at": now,
                    "updated_at": now,
                },
            )

        deleted = 0
        if to_delete:
            ids = [c["cell_id"] if isinstance(c, dict) else str(c) for c in to_delete]
            deleted, _ = CellConfig.objects.filter(
                served_by_du_id=gnb_du_id, cell_id__in=ids,
            ).delete()

        logger.info(
            "DU Config Update DU#%s: add=%d modify=%d delete=%d",
            gnb_du_id, len(to_add), len(to_modify), deleted,
        )

        # 2026-08-12:換場景(cell 增刪改)後重種 intra-gNB 關係 + 清 stale。
        # NRT gating(ANR_REQUIRE_NRT)靠 NrCellRelation 放行換手 —— 換場景不 reseed
        # 會讓新 cell 沒關係、A3 換手被擋 + 殘留舊 cell 關係污染 xApp。冪等,失敗不擋。
        if to_add or to_delete or to_modify:
            try:
                from main.apps.cu_cp.services.business.anr_seeder import seed_from_cells
                seed_from_cells()
            except Exception:
                logger.exception("ANR reseed on DU Config Update failed")

        if to_add or to_delete or to_modify:
            _refresh_neighbours()
        return success_response(
            {"accepted": True, "transaction_id": body.get("transaction_id", 0)},
            "config update accepted",
        )

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def ul_rrc_message(request: HttpRequest):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)

        serializer = UlRrcMessageWriteSerializer(data=body)
        if not serializer.is_valid():
            return error_response("validation failed", serializer.errors, status=400)

        ue_id = serializer.validated_data["ue_id"]
        rrc_msg_b64 = serializer.validated_data["rrc_msg_b64"]
        # Initial UL RRC Message Transfer:UE 在哪個 cell / DU 接入(舊 UE driver 不帶 → 空)
        init_cell = (serializer.validated_data.get("cell_id") or "").strip()
        init_du = serializer.validated_data.get("gnb_du_id")
        if serializer.validated_data.get("is_initial") and init_cell:
            _c = CellConfig.objects.filter(cell_id=init_cell).first()
            if _c is None:
                return error_response(f"cell {init_cell} not served by this gNB", status=404)
            # barred 或正在進入節能(toBeEnergySaving)的 cell 不收新接入 = RRC Reject(TS 38.331 §5.3.3.8);
            # UE 端會改選下一顆 cell。以前只擋換手 / 重建,UE 第一次接入仍會進來,要靠節能背景重試再趕走。
            from main.apps.cu_cp.services.common.fixture_state import admission_blocked
            if admission_blocked(init_cell, bool(_c.is_barred)):
                return error_response(f"cell {init_cell} not accepting access (barred / entering energy saving)",
                                      status=409)

        try:
            decoded = RrcMessageHandler.decode(rrc_msg_b64)
        except ValueError as exc:
            return error_response("corrupt RRC message", str(exc), status=400)

        msg_type = decoded.get("type", "")
        now = TimestampService.now()
        ue_uuid = UUIDService.generate_uuid("ue", ue_id)

        ue = SqlDbBusinessService.get_or_none(UeContext, "ue_id", ue_id)
        if ue is None:
            # 沒真 AMF — 但 xApp / E2 介面要求 amf_ue_ngap_id 唯一可識別。
            # base 由 _resolve_ue_base() 決定:UE_ID_FIXED_MAP(鎖表值)→ UE_ID_RANDOM(隨機)
            # → 預設 SHA-1(決定性穩定)。見該函式註解 + memory ue_id_hash_nondeterminism。
            base = _resolve_ue_base(ue_id)
            # 多 gNB:RAN UE NGAP ID 由各 gNB 自己配(UE 換到別的 gNB 會變,介面 C9);
            # AMF UE NGAP ID 仍是同一個規則(真 AMF 在 Initial Context Setup 時確認)。
            from main.apps.cu_cp.services.business import xn as _xn
            ran = _xn.ran_ue_ngap_id_for(ue_id) if _xn.self_gnb() is not None else base
            ue = SqlDbBusinessService.create_entity(UeContext, {
                "ue_uuid": ue_uuid,
                "ue_id": ue_id,
                "rrc_state": "IDLE",
                "rrc_ue_id": ran,
                "ran_ue_ngap_id": ran,
                "amf_ue_ngap_id": base + 1,    # 跟 ran_ue_ngap_id 差 1 避免混淆
                "created_at": now,
                "updated_at": now,
            })

        next_state = ue.rrc_state
        downstream = {}

        if init_cell:
            # UE 由此 cell 接入:服務 cell 與所在 DU 以 DU 的 Initial UL RRC 為準
            cell_du = CellConfig.objects.filter(cell_id=init_cell).values_list("served_by_du_id", flat=True).first()
            du_id = init_du if init_du is not None else cell_du
            SqlDbBusinessService.update_entity(UeContext, "ue_id", ue_id, {
                "serving_cell": init_cell, "gnb_du_id": du_id, "updated_at": now})
            ue.serving_cell, ue.gnb_du_id = init_cell, du_id
            from main.apps.cu_cp.services.business import ue_notify
            ue_notify.path_update(ue_id, init_cell)

        if msg_type == RrcMessageType.SETUP_REQUEST:
            # UE 以新的 RRC Setup Request 重新接入,本 CU 上舊 context 還停在 RELEASE(剛經 Xn 換走、
            # 或釋放還沒收完)→ 視為新連線,先回 IDLE 再進 SETUP。以前直接 RELEASE → SETUP 丟例外回 500,
            # UE 只能靠重試(單 CU 版就偶發;多 gNB 下 UE 在 gNB 間來回更常見)。
            if ue.rrc_state == "RELEASE":
                ue.rrc_state = RrcStateMachine.transition(ue.rrc_state, "IDLE")
            next_state = RrcStateMachine.transition(ue.rrc_state, "SETUP")
            setup_b64 = RrcMessageHandler.encode_rrc_setup(transaction_id=1)
            downstream = DuClientBusinessService.post_dl_rrc_message(
                F1apHandler.build_dl_rrc_message_transfer(ue_id, setup_b64),
            )
            logger.info("RRC Setup → DU for UE %s", ue_id)
        elif msg_type == RrcMessageType.SETUP_COMPLETE:
            next_state = RrcStateMachine.transition(ue.rrc_state, "CONNECTED")
            ngap_payload = {
                "ran_ue_ngap_id": ue.ran_ue_ngap_id,
                "nas_pdu_b64": decoded.get("payload", {}).get("nas_pdu_b64", ""),
                "selected_plmn": "00101",
                # 真 AMF(多 gNB P5)要知道是哪個 gNB、哪個 UE(SUPI 的替身)、在哪個 cell
                "gnb_id": int(get_str("GNB_ID_HEX", "0x000e00"), 16),
                "ue_id": ue_id,
                "cell_id": ue.serving_cell or "",
            }
            NgapHandler.push_initial_ue_message(ngap_payload)
            logger.info("UE %s reached CONNECTED; InitialUEMessage queued", ue_id)
        elif msg_type == RrcMessageType.RECONFIGURATION_COMPLETE:
            logger.info("UE %s confirmed RRCReconfigurationComplete", ue_id)
        elif msg_type == RrcMessageType.MEASUREMENT_REPORT:
            logger.debug("UE %s sent MeasurementReport via UL RRC (handled in /measurement_report)", ue_id)
        else:
            logger.warning("Unhandled UL RRC message type %s for UE %s", msg_type, ue_id)

        SqlDbBusinessService.update_entity(
            UeContext, "ue_id", ue_id,
            {"rrc_state": next_state, "updated_at": now},
        )

        return success_response({
            "ue_id": ue_id,
            "next_state": next_state,
            "rrc_msg_type": msg_type,
            "downstream": downstream,
        }, "UL RRC processed")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def measurement_report(request: HttpRequest):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)

        serializer = MeasurementReportWriteSerializer(data=body)
        if not serializer.is_valid():
            return error_response("validation failed", serializer.errors, status=400)

        d = serializer.validated_data
        ue_id = d["ue_id"]
        now = TimestampService.now()

        ue = SqlDbBusinessService.get_or_none(UeContext, "ue_id", ue_id)
        if ue is None:
            return error_response(f"unknown UE {ue_id}", status=404)
        # 多 gNB:UE 已經換到別的 gNB(Xn 換手後本地 context 還在等對端的 UE Context Release),
        # 舊 DU 還在路上的報告不能拿來做 ANR / A3 —— 那時的「服務 cell」已經不是本 gNB 的 cell,
        # 會在本 gNB 的 NRT 寫出來源是別人 cell 的關係(2026-09-27 實測)。
        if ue.rrc_state != "CONNECTED" or (ue.serving_cell and not CellConfig.objects.filter(cell_id=ue.serving_cell).exists()):
            return success_response({"ue_id": ue_id, "processed": False}, "UE not served by this gNB (stale report)")

        # 先更新劇本時鐘,再往下做 A3 / RLF 判斷 —— 那些會建立事件,要蓋上「劇本第幾秒」
        from main.apps.cu_cp.services.optional import scene_clock
        scene_clock.update(d.get("scene_sim_ms"))

        # 量測回報門檻(對齊 TS 38.331 reportConfig):真實 UE 只回報達門檻的鄰區,
        # 不是把所有 cell 照報。沒有門檻時「深邊緣稀疏樣本」情境(卷面第3題)做不出來 ——
        # 每台 UE 都會回報每個 cell,樣本永遠不稀疏。
        # env `MEAS_REPORT_MIN_RSRP_DBM`(預設 -110 = 幾乎不濾,保留既有情境行為)。
        from main.utils.env_loader import get_float as _gf2
        _rep_min = _gf2("MEAS_REPORT_MIN_RSRP_DBM", -110.0)
        _nbrs = [n for n in (d.get("neighbor_cells") or [])
                 if n.get("rsrp_dbm") is None or float(n["rsrp_dbm"]) >= _rep_min]
        d["neighbor_cells"] = _nbrs

        SqlDbBusinessService.create_entity(MeasurementLog, {
            "meas_uuid": UUIDService.random_uuid(),
            "ue_id": ue_id,
            "rsrp_dbm": d["rsrp_dbm"],
            "sinr_db": d["sinr_db"],
            "throughput_dl_mbps": d["throughput_dl_mbps"],
            "throughput_ul_mbps": d["throughput_ul_mbps"],
            "mcs_dl": d["mcs_dl"],
            "rb_width_dl": d["rb_width_dl"],
            "mimo_rank": d["mimo_rank"],
            "pdcp_sdu_volume_dl": d.get("pdcp_sdu_volume_dl", 0),
            "pdcp_sdu_volume_ul": d.get("pdcp_sdu_volume_ul", 0),
            "qos_5qi": d.get("qos_5qi", 9),
            "rlc_sdu_delay_dl_ms": d.get("rlc_sdu_delay_dl_ms", 0.0),
            "neighbor_cells_json": d["neighbor_cells"],
            "mcs_ul": d.get("mcs_ul", 0), "rb_width_ul": d.get("rb_width_ul", 0),
            "ul_sinr_db": d.get("ul_sinr_db"), "sinr_layers_json": d.get("sinr_layers_db") or [],
            "beam_id": d.get("beam_id"),
            "window_seq": d.get("window_seq"),
            "scene_sim_ms": d.get("scene_sim_ms"),
            "rsrq_db": d.get("rsrq_db"),
            "cqi": d.get("cqi"),
            "beam_rsrp_top_json": d.get("beam_rsrp_top") or [],
            "serving_cell": ue.serving_cell or "",
            "recorded_at": now,
        })

        # ── gNB 自主 ANR(env ANR_AUTO_ADD,預設關)──
        # 開啟時:量測報告裡沒有鄰區關係的 cell 自己補上,讓 A3 的 NRT gate 放行。
        # 預設關閉的理由見 services/business/anr_auto.py 的說明。
        try:
            from main.apps.cu_cp.services.business import anr_auto, pci_resolution
            if ue.serving_cell:
                if pci_resolution.enabled():
                    # 真實做法:只認 PCI,查不到或查到多個才去解析 CGI。
                    # 這條會讓「缺漏鄰區」「PCI 混淆」真的發生,故預設關閉。
                    pci_resolution.observe(ue.serving_cell, d.get("neighbor_cells") or [])
                elif anr_auto.enabled():
                    # 舊行為:量測報告直接帶 cell_id,等同已完成 PCI→CGI 解析
                    anr_auto.observe_neighbors(
                        ue.serving_cell,
                        [n.get("cell_id") for n in (d.get("neighbor_cells") or []) if n.get("cell_id")],
                    )
        except Exception:  # noqa: BLE001 — ANR 失敗不該影響量測與換手主流程
            logger.exception("自主 ANR 處理失敗 ue=%s", ue_id)

        # ── A3 自動觸發 handover 評估（對齊 OAI rrc_gNB_mobility::trigger_HO） ──
        # 公式：RSRP(neighbor) - hys > RSRP(serving) + offset 持續 TTT_MS
        neighbors = [(n.get("cell_id"), n.get("rsrp_dbm")) for n in (d.get("neighbor_cells") or [])
                     if n.get("cell_id") and n.get("rsrp_dbm") is not None]
        # 服務 cell 沒有量測樣本(rsrp 為 None)這一拍不評估 A3 —— 沒有基準可比
        if neighbors and ue.serving_cell and d["rsrp_dbm"] is not None:
            verdict = A3HandoverCalculation().evaluate(
                ue_state=get_ue_state(ue_id),
                serving_cell=ue.serving_cell,
                serving_rsrp=d["rsrp_dbm"],
                neighbors=neighbors,
            )
            if verdict.triggered and verdict.target_cell:
                from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
                # P2-2:帶 target RSRP → 讓 RandomAccessProblem 失敗原因可判
                _tgt_rsrp = next((r for c, r in neighbors if c == verdict.target_cell), None)
                ho = execute_f1_handover(
                    ue_id=ue_id, target_cell=verdict.target_cell, trigger="A3_TTT",
                    target_rsrp=_tgt_rsrp,
                )
                if ho:
                    logger.info(
                        "A3 auto-trigger handover: ue=%s elapsed_TTT=%dms %s → %s",
                        ue_id, verdict.elapsed_ms, ho["source_cell"], ho["target_cell"],
                    )

        # 用條件式更新:這份報告觸發的換手若把 UE 交給了別的 gNB(NG 換手會刪本地 context),
        # 這裡找不到那一列是正常的。以前用 update_entity 會丟 DoesNotExist → 500 →
        # 整個交易回滾,連剛寫的換手事件一起消失(2026-09-27 NG 換手實測)。
        UeContext.objects.filter(ue_id=ue_id).update(last_measurement_at=now, updated_at=now)

        # ── 2026-08-25 移除 legacy A3 段 ──────────────────────────────
        # 這裡原本還有**第二段** A3:自己建 PREP 事件、直接改 serving_cell,
        # 完全繞過 execute_f1_handover —— 不看 stale-PCI / xnBlocklist /
        # HO_FORCE_FAIL,任何換手失敗建模都擋不住它。上面那段(走 executor)
        # 判 FAILED 之後,這段緊接著把 UE 無條件搬走 —— 第 10 題佈好病、
        # 15 筆 CellNotAvailable 之後 UE 全體「無紀錄地」出現在 b07,就是它幹的。
        # Q7 沒中招純屬僥倖:hoBlocklist 擋在兩段共用的 verdict 層,
        # 而 stale-PCI 防呆只在 executor 層。A3 一律走 execute_f1_handover。
        return success_response({"ue_id": ue_id, "processed": True}, "measurement processed")


    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def rlf_report(request: HttpRequest):
        """P1-1/2:DU 通報 RLF → 落 RlfEvent + 驅動重建決策。

        Body: {ue_id, serving_cell, serving_pci, sinr_at_rlf, t310_ms, reason,
               strongest_cell, strongest_rsrp}
        """
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)
        if not body.get("ue_id"):
            return error_response("ue_id required", status=400)
        # RLF 報告也帶劇本時鐘,而且通常早於第一份量測報告 —— 開場就把時鐘校準,
        # 後續由它衍生的重建/換手事件才不會落成 0
        from main.apps.cu_cp.services.optional import scene_clock
        scene_clock.update(body.get("scene_sim_ms"))
        from main.apps.cu_cp.services.business.reestablishment import handle_rlf
        outcome = handle_rlf(body)
        logger.info("RLF handled: %s", outcome)
        return success_response(outcome, "rlf processed")

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def cell_measurement_report(request: HttpRequest):
        """AL2 — cell-level KPI from DU (3GPP TS 28.552 RRU.PrbTotDl).

        Body: GnbDuCellMeasurementReport dict.
        """
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)

        cell_id = (body.get("cell_id") or "").strip()
        if not cell_id:
            return error_response("cell_id required", status=400)
        # 沒有 UE 在場的視窗只有 cell 報告,時鐘也要跟著走
        from main.apps.cu_cp.services.optional import scene_clock
        scene_clock.update(body.get("scene_sim_ms"))
        try:
            prb_pct_dl = float(body.get("prb_pct_dl", 0.0))
            prb_pct_ul = float(body.get("prb_pct_ul", 0.0))
            tick_count = int(body.get("tick_count", 0))
            window_seconds = float(body.get("window_seconds", 0.0))
        except (TypeError, ValueError) as exc:
            return error_response("invalid numeric field", str(exc), status=400)

        SqlDbBusinessService.create_entity(CellMeasurementLog, {
            "cell_id": cell_id,
            "prb_pct_dl": max(0.0, min(100.0, prb_pct_dl)),
            "prb_pct_ul": max(0.0, min(100.0, prb_pct_ul)),
            "tick_count": tick_count,
            "window_seconds": window_seconds,
            "window_seq": body.get("window_seq"),
            "connected_ues": body.get("connected_ues"),
            "scene_sim_ms": body.get("scene_sim_ms"),
            "recorded_at": TimestampService.now(),
        })
        return success_response({"cell_id": cell_id}, "cell measurement stored")
