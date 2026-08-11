"""E2 Control endpoint — 對齊 OAI E2-SM-RC RIC Control Request。

OAI ref:
  - openair2/E2AP/RAN_FUNCTION/O-RAN/ran_func_rc.c::write_ctrl_rc_sm
  - 支援 Control Style 1 (Radio Bearer Control)
    - Action ID 2: QoS flow mapping configuration
  - 擴展 Style 3 (Mobility Control)
    - Action ID 1: Handover Control（OAI spec 有定義但實作未完成；我們補上）

xApp 透過此端點：
  POST /api/v0.1/CU/E2/Control/request
  body 參考 docstring 內 schema
"""
from __future__ import annotations

import json
from typing import Any

from django.db import transaction
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.services.business.du_client_operations import DuClientBusinessService
from main.apps.cu_cp.services.business.omniverse_push import push_control_action
from main.apps.cu_cp.services.business.sqldb_operations import SqlDbBusinessService
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from main.apps.cu_cp.services.common.uuid_service import UUIDService
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


# ────────────────────────────────────────────────────────────────────
# xApp schema adapters — 我們內部用 ue_id (str) / cell_id (str)，
# 但 OAI / xApp 的 RC wrapper 用 ngap_id / f1ap_id / target_cgi.nr_cell_id。
# 這幾個 helper 把外部標準格式翻成我們內部欄位。
# ────────────────────────────────────────────────────────────────────

def compute_nr_cell_id(cell_id: str, explicit: int | None = None) -> int:
    """Stable cell_id (str) → 36-bit nr_cell_id (int) mapping.

    2026-05-16 P2.2: 改 explicit-first。有 explicit (來自 CellConfig.nr_cellid) 就用,
    沒有再退回 SHA-1 hash(原行為)。
    canonical implementation 在 services.common.cell_id_map。
    """
    from main.apps.cu_cp.services.common.cell_id_map import to_nr_cellid
    return to_nr_cellid(cell_id, explicit=explicit)


def resolve_ue_id(header: dict[str, Any]) -> tuple[str | None, str]:
    """從 xApp 格式的 control_header 取得我們內部 ue_id。

    支援三種輸入（按優先順序）：
      1. ue_id (str)              — 我們既有
      2. ngap_id (int)            — xApp wrapper 的 AMF-UE-NGAP-ID
      3. f1ap_id (int)            — xApp wrapper 的 gNB-CU-UE-F1AP-ID

    Returns: (ue_id, source) — source 標明從哪個欄位解析來，方便 log。
    """
    if header.get("ue_id"):
        return header["ue_id"], "ue_id"

    ngap_id = header.get("ngap_id")
    if ngap_id is not None and ngap_id != 0:
        ue = UeContext.objects.filter(amf_ue_ngap_id=int(ngap_id)).first()
        if ue:
            return ue.ue_id, f"ngap_id={ngap_id}"

    f1ap_id = header.get("f1ap_id")
    if f1ap_id is not None and f1ap_id != 0:
        ue = UeContext.objects.filter(rrc_ue_id=int(f1ap_id)).first()
        if ue:
            return ue.ue_id, f"f1ap_id={f1ap_id}"

    return None, "unresolved"


def resolve_target_cell(message: dict[str, Any]) -> tuple[str | None, str]:
    """從 xApp 格式的 control_message 取得我們內部 cell_id。

    支援三種輸入（按優先順序）：
      1. target_cell (str)                  — 我們既有
      2. target_cgi.cell_id (str)           — xApp 也常用 string CGI
      3. target_cgi.nr_cell_id (int)        — 36-bit NR cell identity

    Returns: (cell_id, source).
    """
    if message.get("target_cell"):
        return message["target_cell"], "target_cell"

    cgi = message.get("target_cgi") or {}
    if cgi.get("cell_id"):
        return cgi["cell_id"], "target_cgi.cell_id"

    nr_id = cgi.get("nr_cell_id")
    if nr_id is not None:
        # 2026-05-16 P2.5: 走集中化 helper,先精確比對 nr_cellid 欄位再退回 hash 反查
        from main.apps.cu_cp.services.common.cell_id_map import to_platform_cell_id
        target = int(nr_id)
        platform_id = to_platform_cell_id(target)
        if platform_id:
            return platform_id, f"nr_cell_id={target}"

    return None, "unresolved"


logger = get_logger(__name__)


class E2ControlActor:
    """OAI ref: ran_func_rc.c::write_ctrl_rc_sm

    支援的 (style, action) 組合：
      (1, 2) = Radio Bearer Control / QoS flow mapping     ← OAI 標準
      (3, 1) = Mobility Control / Handover Control         ← 我們擴展（adapter 接 xApp schema）
      (2, 6) = Radio Resource Allocation / Slice-level PRB Quota   ← xApp IM/ES 用
                  control_header.cell_id 或 .node
                  control_message.{min_prb, max_prb, dedicated_prb} (0-100)
      (2, 7) = Radio Resource Allocation / Cell On/Off     ← Energy-saving xApp 用
                  control_header.cell_id required
                  control_message.action: 'enable' | 'disable'
    """

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def request(request: HttpRequest):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError as e:
            return error_response("Invalid JSON", str(e), status=400)

        ric_req_id = body.get("ric_req_id") or {}
        ran_func_id = body.get("ran_function_id")

        # ── E2SM-CCC cell 開關:adapter 送 {sim_action:control_cell_onoff, cells:[{cell_id, action}]}──
        # 不走 RC 的 (style, action);逐 cell 套用既有 _handle_cell_on_off(硬開關)。
        # 兩階段節能(toBeEnergySaving→趕人→isEnergySaving)為後續增強。
        if body.get("sim_action") == "control_cell_onoff" or body.get("cells"):
            applied, failed = [], []
            for c in body.get("cells") or []:
                cid = c.get("cell_id")
                act = c.get("action")  # "enable" | "disable"
                if not cid or act not in ("enable", "disable"):
                    failed.append({"cell": cid, "reason": "bad cell_id/action"})
                    continue
                if c.get("staged"):
                    # 節能兩階段:toBeEnergySaving→趕人→isEnergySaving(或開回)
                    applied.append(_cell_energy_saving(cid, act, ric_req_id))
                else:
                    # 硬開關(administrativeState LOCKED/UNLOCKED):即時
                    _handle_cell_on_off(cid, {"action": act}, ric_req_id)
                    applied.append({"cell_id": cid, "action": act, "mode": "hard"})
            return success_response(
                {"ric_req_id": ric_req_id, "service_model": "CCC",
                 "applied": applied, "failed": failed},
                "CCC cell control acknowledged",
            )

        header = body.get("control_header") or {}
        message = body.get("control_message") or {}

        cell_id = header.get("cell_id")    # cell-level control 用
        style = header.get("control_style")
        action_id = header.get("control_action_id")

        if style is None or action_id is None:
            return error_response(
                "control_header must contain control_style, control_action_id",
                status=400,
            )

        # Routing：對齊 OAI E2-SM-RC 的 (style, action) 組合
        if style == 1 and action_id == 2:
            ue_id, _src = resolve_ue_id(header)
            if not ue_id:
                return error_response("ue_id (or ngap_id/f1ap_id) required for style=1", status=400)
            return _handle_qos_flow_mapping(ue_id, message, ric_req_id)
        if style == 3 and action_id == 1:
            ue_id, ue_src = resolve_ue_id(header)
            if not ue_id:
                return error_response(
                    "could not resolve UE — provide ue_id, or ngap_id (AMF-UE-NGAP-ID), or f1ap_id (gNB-CU-UE-F1AP-ID)",
                    status=400,
                )
            return _handle_handover(ue_id, message, ric_req_id, ue_src=ue_src)
        if style == 2 and action_id == 6:
            return _handle_slice_prb_quota(header, message, ric_req_id)
        if style == 2 and action_id == 7:
            if not cell_id:
                return error_response("cell_id required for style=2 action=7 (cell on/off)", status=400)
            return _handle_cell_on_off(cell_id, message, ric_req_id)

        return _es_unsupported_response(style, action_id)

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def cell_es_state(request: HttpRequest):
        """回傳各 cell 的 energySavingState — 給 E2Adapter CCC Indication producer 輪詢。"""
        return success_response(get_cell_es_state(), "cell ES state")


def _es_unsupported_response(style, action_id):
    return error_response(
        f"unsupported (control_style={style}, control_action_id={action_id})",
        status=400,
        )


# ────────────────────────────────────────────────────────────
# (Style 1, Action 2) QoS Flow Mapping — OAI 標準支援的
# ────────────────────────────────────────────────────────────

def _handle_qos_flow_mapping(
    ue_id: str, message: dict[str, Any], ric_req_id: dict[str, int]
) -> Any:
    """
    對齊 OAI ran_func_rc.c::write_ctrl_rc_sm (style=1, action=2)
    message:
      drb_id: int
      qos_flows: [ {qfi, direction}, ... ]
    """
    drb_id = message.get("drb_id")
    qos_flows = message.get("qos_flows") or []
    if drb_id is None:
        return error_response("control_message.drb_id required", status=400)
    logger.info(
        "E2 Control [QoS flow mapping] ue=%s drb=%s flows=%s ric_req=%s",
        ue_id, drb_id, qos_flows, ric_req_id,
    )
    push_control_action(
        control_style=1, control_action_id=2,
        action_label="QOS_FLOW_MAPPING",
        ric_req_id=ric_req_id, ue_name=ue_id,
        payload_json={"drb_id": drb_id, "qos_flows": qos_flows},
        outcome="QOS_FLOW_MAPPING_APPLIED",
        action_ts=TimestampService.now().isoformat(),
    )
    # 真機會呼 CU-UP E1AP；我們 sim 端只 log + 回 ack
    return success_response(
        {
            "ric_req_id": ric_req_id,
            "ue_id": ue_id,
            "control_outcome": "QOS_FLOW_MAPPING_APPLIED",
            "drb_id": drb_id,
            "qos_flows": qos_flows,
        },
        "control acknowledged",
    )


# ────────────────────────────────────────────────────────────
# (Style 3, Action 1) Handover Control — 我們擴展
# ────────────────────────────────────────────────────────────

def _handle_handover(
    ue_id: str,
    message: dict[str, Any],
    ric_req_id: dict[str, int],
    *,
    ue_src: str = "ue_id",
) -> Any:
    """xApp trigger handover。對齊 OAI E2-SM-RC Style 3 / Action 1 (`nr_HO_F1_trigger`)。

    Accepts both schemas:
      內部簡化:    {"target_cell": "gnb_alpha_c0"}
      xApp wrapper: {"target_cgi": {"plmn": {...}, "nr_cell_id": 12345678}}
                    (我們忽略 plmn，只用 nr_cell_id 反查 cell_id)
    """
    target_cell, cell_src = resolve_target_cell(message)
    if not target_cell:
        return error_response(
            "could not resolve target — provide target_cell, or target_cgi.cell_id, or target_cgi.nr_cell_id",
            status=400,
        )

    ue_pre = SqlDbBusinessService.get_or_none(UeContext, "ue_id", ue_id)
    if ue_pre is None:
        return error_response(f"unknown UE {ue_id} (resolved from {ue_src})", status=404)
    source_cell_pre = ue_pre.serving_cell or ""

    # 走 handover_executor: 寫 HandoverEvent + UPDATE UeContext.serving_cell
    # + F1AP UE Context Modification 通知 DU (這層之前 _handle_handover 缺)
    # + AA4 defensive guard (target_cell 必須在 CellConfig 中)
    from main.apps.cu_cp.services.business.handover_executor import execute_f1_handover
    result = execute_f1_handover(
        ue_id=ue_id, target_cell=target_cell, trigger="E2_RIC_CONTROL",
    )
    if result is None:
        return error_response(
            f"handover failed: target_cell={target_cell!r} not in CellConfig "
            f"or UE state issue (ue={ue_id})",
            status=400,
        )
    if result.get("skipped"):
        logger.info("E2 Control [Handover] ue=%s already on target=%s, skip",
                    ue_id, target_cell)

    logger.info(
        "E2 Control [Handover] ue=%s (via %s) %s → %s (via %s) ric_req=%s",
        ue_id, ue_src, source_cell_pre, target_cell, cell_src, ric_req_id,
    )
    push_control_action(
        control_style=3, control_action_id=1,
        action_label="HANDOVER",
        ric_req_id=ric_req_id, ue_name=ue_id, cell_id=target_cell,
        payload_json={
            "source_cell": source_cell_pre,
            "target_cell": target_cell,
            "ue_resolved_from": ue_src,
            "target_resolved_from": cell_src,
            "ho_uuid": result.get("ho_uuid", ""),
        },
        outcome="HANDOVER_TRIGGERED" if not result.get("skipped") else "HANDOVER_SKIPPED",
        action_ts=TimestampService.now().isoformat(),
    )
    return success_response(
        {
            "ric_req_id": ric_req_id,
            "ue_id": ue_id,
            "ue_resolved_from": ue_src,
            "control_outcome": "HANDOVER_TRIGGERED",
            "ho_uuid": result.get("ho_uuid", ""),
            "source_cell": source_cell_pre,
            "target_cell": target_cell,
            "target_resolved_from": cell_src,
            # P2.2: 用 target_cell 對應 CellConfig.nr_cellid (explicit) 編出真正 nr_cell_id;沒有就 hash
            "target_nr_cell_id": compute_nr_cell_id(
                target_cell,
                explicit=CellConfig.objects.filter(cell_id=target_cell)
                .values_list("nr_cellid", flat=True)
                .first(),
            ),
            "ngap_id": ue_pre.amf_ue_ngap_id,
            "f1ap_id": ue_pre.rrc_ue_id,
        },
        "control acknowledged",
    )


# ────────────────────────────────────────────────────────────
# (Style 2, Action 6) Slice-level PRB Quota — IM / ES xApp
# 對齊 OAI E2-SM-RC `control_slice_level_prb_quota`
# ────────────────────────────────────────────────────────────

def _handle_slice_prb_quota(
    header: dict[str, Any], message: dict[str, Any], ric_req_id: dict[str, int]
) -> Any:
    """xApp wrapper: control_slice_level_prb_quota(node, ue, min_prb, max_prb, dedicated_prb).

    映射：
      cell 解析優先順序：control_header.cell_id > control_header.node (作 gnb_id 用)
      ratio：control_message.{min_prb, max_prb, dedicated_prb}（必填）

    `node` 對應 xApp 的 gNB-CU meid。在我們架構等同於 gnb_id（標籤 grouping）。
    給 node 時會把 quota 套到該 gNB 下所有 cells（single-cell 情況等同於 cell_id）。

    `ue` 索引 xApp spec 註明 single-slice 固定 0 — 我們忽略。
    """
    cell_id = header.get("cell_id")
    node = header.get("node")

    targets: list[str] = []
    if cell_id:
        targets = [cell_id]
    elif node:
        # node 視為 gnb_id，套用到該 gNB 所有 cell
        targets = list(
            CellConfig.objects.filter(gnb_id=node).values_list("cell_id", flat=True)
        )
        if not targets:
            # 沒對到 sim 內部 gnb_id (例如 'gnb4'). 看是不是 R-NIB inventoryName 形式
            # `gnb_<MCC>_<MNC_padded>_<gnb_id_hex>` 並對應 globalE2node-ID 衍生值.
            from main.apps.cu_cp.services.optional.e2.global_e2_node_id import (
                read_global_e2_node_id,
            )
            try:
                e2_id = read_global_e2_node_id()
                expected_ran_name = e2_id.get("expected_ran_name", "")
            except Exception:
                expected_ran_name = ""
            matched_self = bool(expected_ran_name) and node == expected_ran_name

            targets = list(
                CellConfig.objects.filter(is_active=True).values_list("cell_id", flat=True)
            )
            if not targets:
                return error_response(
                    f"node '{node}' has no matching cells and no active cells available",
                    status=404,
                )
            if matched_self:
                logger.info(
                    "PRB quota: node=%r matched globalE2node-ID for this sim, applying to all %d active cells",
                    node, len(targets),
                )
            else:
                logger.info(
                    "PRB quota: node=%r 不對應 sim gnb_id 也非 R-NIB inventoryName, fallback 套全 %d active cells",
                    node, len(targets),
                )
    else:
        # 完全沒給 node/cell_id → 套全部 active cells
        targets = list(
            CellConfig.objects.filter(is_active=True).values_list("cell_id", flat=True)
        )
        if not targets:
            return error_response(
                "control_header missing 'cell_id'/'node' and no active cells available",
                status=400,
            )

    # 驗 ratio
    def _pct(name: str, default: int) -> tuple[int | None, str | None]:
        v = message.get(name)
        if v is None:
            return default, None
        try:
            iv = int(v)
        except (TypeError, ValueError):
            return None, f"control_message.{name} must be int 0-100"
        if iv < 0 or iv > 100:
            return None, f"control_message.{name} must be 0-100, got {iv}"
        return iv, None

    min_prb, err = _pct("min_prb", 0)
    if err: return error_response(err, status=400)
    max_prb, err = _pct("max_prb", 100)
    if err: return error_response(err, status=400)
    dedicated, err = _pct("dedicated_prb", 100)
    if err: return error_response(err, status=400)

    if min_prb > max_prb:
        return error_response(
            f"min_prb ({min_prb}) > max_prb ({max_prb}) — invalid", status=400,
        )

    # 對每個 target cell 呼 DU
    results = []
    failures = []
    for tc in targets:
        resp = DuClientBusinessService.post_set_prb_quota(
            tc, min_prb=min_prb, max_prb=max_prb, dedicated_prb=dedicated, set_by="xApp",
        )
        ok = bool(resp.get("success") or (resp.get("status") == "success"))
        if ok:
            results.append({
                "cell_id": tc, "min_prb": min_prb, "max_prb": max_prb, "dedicated_prb": dedicated,
            })
        else:
            failures.append({"cell_id": tc, "error": resp.get("message") or resp.get("error", "?")})

    logger.info(
        "E2 Control [PRB Quota] node=%s cells=%s min=%s max=%s dedicated=%s ok=%d fail=%d",
        node, targets, min_prb, max_prb, dedicated, len(results), len(failures),
    )

    outcome_str = "PRB_QUOTA_APPLIED" if not failures else "PRB_QUOTA_PARTIAL"
    push_control_action(
        control_style=2, control_action_id=6,
        action_label="PRB_QUOTA",
        ric_req_id=ric_req_id,
        cell_id=(targets[0] if len(targets) == 1 else None),
        payload_json={
            "node": node, "cells": targets,
            "min_prb": min_prb, "max_prb": max_prb, "dedicated_prb": dedicated,
            "applied": results, "failed": failures,
        },
        outcome=outcome_str,
        error=(f"{failures}" if failures and not results else None),
        action_ts=TimestampService.now().isoformat(),
    )

    if failures and not results:
        return error_response(
            f"DU rejected all cells: {failures}", status=502,
        )

    return success_response(
        {
            "ric_req_id": ric_req_id,
            "control_outcome": outcome_str,
            "applied": results,
            "failed": failures,
        },
        "control acknowledged",
    )


# ────────────────────────────────────────────────────────────
# (Style 2, Action 7) Cell On/Off — energy saving xApp
# ────────────────────────────────────────────────────────────

def _handle_cell_on_off(
    cell_id: str, message: dict[str, Any], ric_req_id: dict[str, int]
) -> Any:
    """E2-SM-RC Style 2 (Radio Resource Allocation) Action 7 — Cell On/Off。

    對齊：OAI 規範 Style 2 是 cell-level 資源控制；action_id 為實作擴展。
    message: {"action": "enable" | "disable"}
    效果：CU 轉發給 DU 的 MacCellController.enable/disable，
          DU 端會：
            • 改 CellState.is_active
            • 通知 CU via gNB-DU Configuration Update（CellConfig 同步）
            • tick driver 略過 inactive cell（FAPI 不發給 RU）
    """
    action = (message.get("action") or "").lower()
    if action not in ("enable", "disable"):
        return error_response(
            "control_message.action must be 'enable' or 'disable'", status=400,
        )

    if action == "disable":
        resp = DuClientBusinessService.post_cell_disable(cell_id)
    else:
        resp = DuClientBusinessService.post_cell_enable(cell_id)

    accepted = bool(resp.get("success") or (resp.get("status") == "success"))
    logger.info(
        "E2 Control [Cell On/Off] cell=%s action=%s ric_req=%s accepted=%s",
        cell_id, action, ric_req_id, accepted,
    )
    push_control_action(
        control_style=2, control_action_id=7,
        action_label=f"CELL_{action.upper()}",
        ric_req_id=ric_req_id, cell_id=cell_id,
        payload_json={"action": action},
        outcome=f"CELL_{action.upper()}D" if accepted else "CELL_ACTION_REJECTED",
        error=(None if accepted else (resp.get("message") or resp.get("error", "unknown"))),
        action_ts=TimestampService.now().isoformat(),
    )
    if not accepted:
        return error_response(
            f"DU rejected cell {action}: {resp.get('message') or resp.get('error', 'unknown')}",
            status=502,
        )
    return success_response(
        {
            "ric_req_id": ric_req_id,
            "cell_id": cell_id,
            "control_outcome": f"CELL_{action.upper()}D",
            "du_response": resp.get("data") or resp.get("message"),
        },
        "control acknowledged",
    )


# ── E2SM-CCC 節能兩階段狀態機(toBeEnergySaving → 趕人(HO) → isEnergySaving)──
# CU 負責編排:HO 是 CU/RRC 職責;cell RF 開關經 F1AP 給 DU 執行。
_CELL_ES_STATE: dict[str, str] = {}   # cell_id → isNotEnergySaving | toBeEnergySaving | isEnergySaving


def get_cell_es_state(cell_id: str | None = None):
    """給 adapter CCC Indication producer 輪詢用。"""
    if cell_id:
        return _CELL_ES_STATE.get(cell_id, "isNotEnergySaving")
    return dict(_CELL_ES_STATE)


def _pick_offload_target(es_cell_id: str) -> str | None:
    """趕人目標:其它 cell(排除本 cell + 正在節能的 cell)。2-cell DT = 同站另一 cell。
    (RSRP-best 精選為 TODO;先用第一個可用鄰 cell。)"""
    for cid in CellConfig.objects.exclude(cell_id=es_cell_id).values_list("cell_id", flat=True):
        if _CELL_ES_STATE.get(cid, "isNotEnergySaving") == "isNotEnergySaving":
            return cid
    return None


def _cell_energy_saving(cell_id: str, action: str, ric_req_id: dict) -> dict:
    """action='disable' → toBeEnergySaving(趕人後關);'enable' → toBeNotEnergySaving(開回)。"""
    if action == "enable":
        DuClientBusinessService.post_cell_enable(cell_id)
        _CELL_ES_STATE[cell_id] = "isNotEnergySaving"
        push_control_action(
            control_style=2, control_action_id=7, action_label="CELL_ES_EXIT",
            ric_req_id=ric_req_id, cell_id=cell_id,
            payload_json={"energySavingState": "isNotEnergySaving"},
            outcome="isNotEnergySaving", action_ts=TimestampService.now().isoformat(),
        )
        logger.info("ES: cell %s → isNotEnergySaving (enabled)", cell_id)
        return {"cell_id": cell_id, "energySavingState": "isNotEnergySaving"}

    # disable → toBeEnergySaving:先趕人,清空才關
    _CELL_ES_STATE[cell_id] = "toBeEnergySaving"
    target = _pick_offload_target(cell_id)
    ues = list(UeContext.objects.filter(serving_cell=cell_id, rrc_state="CONNECTED"))
    offloaded, failed = [], []
    for ue in ues:
        if not target:
            failed.append(ue.ue_id)
            continue
        try:
            _handle_handover(ue.ue_id, {"target_cell": target}, ric_req_id, ue_src="es")
            offloaded.append({"ue": ue.ue_id, "target": target})
        except Exception as e:  # noqa: BLE001
            logger.warning("ES offload HO failed ue=%s: %s", ue.ue_id, e)
            failed.append(ue.ue_id)

    remaining = UeContext.objects.filter(serving_cell=cell_id, rrc_state="CONNECTED").count()
    if remaining == 0:
        DuClientBusinessService.post_cell_disable(cell_id)
        _CELL_ES_STATE[cell_id] = "isEnergySaving"
        state = "isEnergySaving"
        logger.info("ES: cell %s cleared (%d UE offloaded) → isEnergySaving (disabled)",
                    cell_id, len(offloaded))
    else:
        state = "toBeEnergySaving"
        logger.info("ES: cell %s still has %d UE → stay toBeEnergySaving (not disabled yet)",
                    cell_id, remaining)
    push_control_action(
        control_style=2, control_action_id=7, action_label="CELL_ES_ENTER",
        ric_req_id=ric_req_id, cell_id=cell_id,
        payload_json={"energySavingState": state, "offloaded": offloaded,
                      "target_cell": target, "remaining": remaining},
        outcome=state, action_ts=TimestampService.now().isoformat(),
    )
    return {"cell_id": cell_id, "energySavingState": state,
            "offloaded": offloaded, "failed": failed, "remaining": remaining}
