"""E2SM-RC codec — Control Header / Message decoder + extract sim CU payload.

Reference:
  - O-RAN E2SM-RC v01.03 §7.5 (Control Service)
  - intents-interface.md §3 RC Wrapper API:
      Style 2 / Action 6 — control_slice_level_prb_quota (IM, ES)
      Style 3 / Action 1 — control_handover (CCO, ES)

E2SM-RC-ControlHeader Format1:
  { ueID, ric-Style-Type, ric-ControlAction-ID, ric-ControlDecision }

E2SM-RC-ControlMessage Format1:
  { ranP-List: [Format1-Item{ ranParameter-ID, ranParameter-valueType }] }

ranParameter-valueType is CHOICE { ElementFalse, ElementTrue, List, Structure }
ElementTrue/False 內含 RANParameter-Value CHOICE
  { valueBoolean, valueInt, valueReal, valueBitS, valueOctS, valuePrintableString }
"""
from __future__ import annotations

from typing import Any

from main.apps.e2_adapter.services.optional.codec.e2ap_codec import _load_runtime


def _rc_v10_enabled() -> bool:
    import os
    return (os.environ.get("RC_MODULE_V10") or "off").strip().lower() in ("on", "1", "true")


def _rc_ies():
    """RC 結構類別的來源。

    RC_MODULE_V10=on → RIC 提供的 pycrate 預編譯模組(含 ControlHeader Format 3 /
    UE Group / ueGroup-ControlAction-Supported;共存性 2026-08-25 已實測:與執行期
    編譯的 E2AP+KPM 同 process,KPM 三次往返位元組一致)。
    off → 沿用執行期編譯的 e2sm_rc_v01.03(現行為,無 Format 3)。
    只有 RC 的 E2SM 內層走這裡;E2AP 外層一律走 _load_runtime()。
    """
    if _rc_v10_enabled():
        from main.apps.e2_adapter.services.optional.codec import e2sm_rc_precompiled as _pc
        return _pc.E2SM_RC_IEs
    return _load_runtime().E2SM_RC_IEs
from main.utils.logger import get_logger

logger = get_logger(__name__)


# ── Decode helpers ───────────────────────────────────────────────

def _flatten_ueid(ueid_choice: tuple) -> dict[str, Any]:
    """Flatten UEID CHOICE → simple dict {kind, amf_ue_ngap_id, gnb_cu_f1ap_id, ...}."""
    if not isinstance(ueid_choice, tuple) or len(ueid_choice) != 2:
        return {"kind": "unknown"}
    kind, val = ueid_choice
    out: dict[str, Any] = {"kind": kind}
    if isinstance(val, dict):
        # gNB-UEID has amf-UE-NGAP-ID + guami + gNB-CU-UE-F1AP-ID-List
        if "amf-UE-NGAP-ID" in val:
            out["amf_ue_ngap_id"] = int(val["amf-UE-NGAP-ID"])
        if "gNB-CU-UE-F1AP-ID-List" in val:
            f1_list = val["gNB-CU-UE-F1AP-ID-List"] or []
            if f1_list:
                first = f1_list[0]
                out["gnb_cu_ue_f1ap_id"] = int(first.get("gNB-CU-UE-F1AP-ID", 0))
        if "guami" in val:
            g = val["guami"]
            plmn = g.get("pLMNIdentity")
            if plmn:
                out["plmn_hex"] = plmn.hex() if isinstance(plmn, (bytes, bytearray)) else str(plmn)
    return out


def _scalarize(scalar_kind: str, scalar_val: Any) -> Any:
    """Convert pycrate ASN.1 scalar → JSON-safe Python value.

    BIT STRING 在 pycrate 是 (int, bit_count) tuple; OCTET STRING 是 bytes.
    """
    if scalar_kind in ("valueBitS",):
        if isinstance(scalar_val, tuple) and len(scalar_val) == 2:
            return {"int": int(scalar_val[0]), "bits": int(scalar_val[1])}
        return scalar_val
    if scalar_kind in ("valueOctS",):
        if isinstance(scalar_val, (bytes, bytearray)):
            return scalar_val.hex()
        return str(scalar_val)
    if scalar_kind in ("valueInt", "valueReal"):
        return scalar_val
    if scalar_kind == "valueBoolean":
        return bool(scalar_val)
    if scalar_kind in ("valuePrintableString",):
        return str(scalar_val)
    return scalar_val


def _unwrap_ranparameter_value(value_type_choice: tuple) -> Any:
    """Unwrap RANParameter-ValueType CHOICE → return JSON-safe scalar/nested dict.

    Returns one of:
      - {"_type": <scalar_kind>, "value": <json-safe value>}     ElementTrue/False
      - {"_type": "structure", "fields": {child_id: <recursive>}} Structure
      - {"_type": "list", "items": [<dict per item>]}            List
      - None
    """
    if not isinstance(value_type_choice, tuple) or len(value_type_choice) != 2:
        return None
    vt_kind, vt_val = value_type_choice
    if vt_kind in ("ranP-Choice-ElementTrue", "ranP-Choice-ElementFalse"):
        rp_val = vt_val.get("ranParameter-value") if isinstance(vt_val, dict) else None
        if isinstance(rp_val, tuple) and len(rp_val) == 2:
            scalar_kind, scalar_val = rp_val
            return {"_type": scalar_kind, "value": _scalarize(scalar_kind, scalar_val)}
        return None
    if vt_kind == "ranP-Choice-Structure":
        struct = vt_val.get("ranParameter-Structure") if isinstance(vt_val, dict) else None
        seq = struct.get("sequence-of-ranParameters") if isinstance(struct, dict) else None
        fields: dict[int, Any] = {}
        for item in seq or []:
            child_id = int(item.get("ranParameter-ID", 0))
            child_val = _unwrap_ranparameter_value(item.get("ranParameter-valueType"))
            fields[child_id] = child_val
        return {"_type": "structure", "fields": fields}
    if vt_kind == "ranP-Choice-List":
        lst = vt_val.get("ranParameter-List") if isinstance(vt_val, dict) else None
        seq = lst.get("list-of-ranParameter") if isinstance(lst, dict) else None
        items: list[Any] = []
        for entry in seq or []:
            entry_seq = entry.get("sequence-of-ranParameters") if isinstance(entry, dict) else None
            entry_fields: dict[int, Any] = {}
            for item in entry_seq or []:
                child_id = int(item.get("ranParameter-ID", 0))
                child_val = _unwrap_ranparameter_value(item.get("ranParameter-valueType"))
                entry_fields[child_id] = child_val
            items.append({"fields": entry_fields})
        return {"_type": "list", "items": items}
    return None


def decode_ric_control_request(data: bytes) -> dict[str, Any]:
    """Decode RIC Control Request → dict ready for sim CU /Control/request.

    Returns:
      {
        "ric_req_id": {requestor_id, instance_id},
        "ran_function_id": int,
        "style_type": int,
        "action_id": int,
        "ueid": {kind, amf_ue_ngap_id, gnb_cu_ue_f1ap_id, plmn_hex},
        "ran_params": {param_id: {value/_type/_nested}},
        "decision": str,
        "raw_header_bytes": int,
        "raw_message_bytes": int,
      }
    """
    rt = _load_runtime()
    pdu_cls = rt.E2AP_PDU_Descriptions.E2AP_PDU
    pdu_cls.from_aper(data)
    decoded = pdu_cls.get_val()

    outcome_choice, outcome_val = decoded
    if outcome_choice != "initiatingMessage":
        raise ValueError(f"expected initiatingMessage, got {outcome_choice}")

    inner = outcome_val["value"]
    if inner[0] != "RICcontrolRequest":
        raise ValueError(f"expected RICcontrolRequest, got {inner[0]}")

    ctrl_req = inner[1]

    ric_req_id = {"requestor_id": 0, "instance_id": 0}
    ran_function_id = 0
    header_bytes = b""
    message_bytes = b""
    call_process_id = b""
    decision = ""

    # ProtocolIE IDs (E2AP §9.2.2)
    IE_RICrequestID = 29
    IE_RANfunctionID = 5
    IE_RICcallProcessID = 20
    IE_RICcontrolHeader = 22
    IE_RICcontrolMessage = 23
    IE_RICcontrolAckRequest = 21

    for ie in ctrl_req.get("protocolIEs", []):
        ie_id = ie.get("id")
        ie_value = ie.get("value")
        if not isinstance(ie_value, tuple):
            continue
        _, val = ie_value
        if ie_id == IE_RICrequestID:
            ric_req_id = {
                "requestor_id": val.get("ricRequestorID", 0),
                "instance_id": val.get("ricInstanceID", 0),
            }
        elif ie_id == IE_RANfunctionID:
            ran_function_id = int(val)
        elif ie_id == IE_RICcontrolHeader:
            header_bytes = bytes(val) if not isinstance(val, bytes) else val
        elif ie_id == IE_RICcontrolMessage:
            message_bytes = bytes(val) if not isinstance(val, bytes) else val
        elif ie_id == IE_RICcallProcessID:
            call_process_id = bytes(val) if not isinstance(val, bytes) else val
        elif ie_id == IE_RICcontrolAckRequest:
            decision = str(val)

    # Decode E2SM-RC ControlHeader (Format 1)
    style_type = 0
    action_id = 0
    ueid_dict: dict[str, Any] = {"kind": "unknown"}
    try:
        ch_cls = _rc_ies().E2SM_RC_ControlHeader
        ch_cls.from_aper(header_bytes)
        ch_val = ch_cls.get_val()
        fmt_choice, fmt_val = ch_val.get("ric-controlHeader-formats", (None, {}))
        if fmt_choice == "controlHeader-Format1":
            style_type = int(fmt_val.get("ric-Style-Type", 0))
            action_id = int(fmt_val.get("ric-ControlAction-ID", 0))
            ueid_dict = _flatten_ueid(fmt_val.get("ueID", (None, {})))
        elif fmt_choice == "controlHeader-Format3":
            # UE Group 控制(v10 第 5 題):群組=條件式,UE 識別不外流(L1)。
            style_type = int(fmt_val.get("ric-Style-Type", 0))
            action_id = int(fmt_val.get("ric-ControlAction-ID", 0))
            items = []
            for it in (fmt_val.get("ue-Group-Definition", {})
                       .get("ueGroupDefinitionIdentifier-LIST", []) or []):
                items.append({
                    "ranParameter_id": int(it.get("ranParameter-ID", 0)),
                    "value": _unwrap_ranparameter_value(it.get("ranParameter-valueType")),
                    "logicalOR": str(it.get("logicalOR", "false")),  # 名稱比對,勿比 0/1
                })
            ueid_dict = {"kind": "group",
                         "ue_group_id": int(fmt_val.get("ue-Group-ID", 0)),
                         "conditions": items}
    except Exception as exc:
        logger.warning("decode E2SM-RC ControlHeader failed: %s", exc)

    # Decode E2SM-RC ControlMessage (Format 1) — extract ranP list
    ran_params: dict[int, Any] = {}
    try:
        cm_cls = _rc_ies().E2SM_RC_ControlMessage
        cm_cls.from_aper(message_bytes)
        cm_val = cm_cls.get_val()
        fmt_choice, fmt_val = cm_val.get("ric-controlMessage-formats", (None, {}))
        if fmt_choice == "controlMessage-Format1":
            for item in fmt_val.get("ranP-List", []) or []:
                pid = int(item.get("ranParameter-ID", 0))
                pvalue = _unwrap_ranparameter_value(item.get("ranParameter-valueType"))
                ran_params[pid] = pvalue
    except Exception as exc:
        logger.warning("decode E2SM-RC ControlMessage failed: %s", exc)

    return {
        "ric_req_id": ric_req_id,
        "ran_function_id": ran_function_id,
        "style_type": style_type,
        "action_id": action_id,
        "ueid": ueid_dict,
        "ran_params": ran_params,
        "decision": decision,
        "raw_header_bytes": len(header_bytes),
        "raw_message_bytes": len(message_bytes),
        "call_process_id": call_process_id.hex() if call_process_id else "",
    }


# ── Map RC Control → sim CU /CU/E2/Control/request payload ──────

def _extract_target_cgi(params: dict) -> dict:
    """從 ranP 抽 Target CGI → {plmn_hex, nr_cell_id}。逐 UE 3-1 與群組 Format 3 共用同源
    (spec structure walk + rc-probe 打包式 valueOctS fallback)。"""
    plmn_hex = ""
    nr_cell_id_int = 0

    def _walk(node):
        nonlocal plmn_hex, nr_cell_id_int
        if not isinstance(node, dict):
            return
        t = node.get("_type")
        if t == "valueOctS" and not plmn_hex:
            v = node.get("value")
            if isinstance(v, str) and len(v) == 6:
                plmn_hex = v
        elif t == "valueBitS" and not nr_cell_id_int:
            v = node.get("value")
            if isinstance(v, dict) and v.get("bits") in (36, 28):
                nr_cell_id_int = int(v.get("int", 0))
        elif t == "structure":
            for child in (node.get("fields") or {}).values():
                _walk(child)
        elif t == "list":
            for item in node.get("items") or []:
                for child in (item.get("fields") or {}).values():
                    _walk(child)

    for _pv in params.values():
        _walk(_pv)
    if not (plmn_hex and nr_cell_id_int):
        for _pv in params.values():
            if isinstance(_pv, dict) and _pv.get("_type") == "valueOctS":
                h = _pv.get("value") or ""
                if isinstance(h, str) and len(h) >= 16:
                    cgi = bytes.fromhex(h)[-8:]
                    plmn_hex = plmn_hex or cgi[0:3].hex()
                    nr_cell_id_int = nr_cell_id_int or (int.from_bytes(cgi[3:8], "big") >> 4)
                    break
    out = {}
    if plmn_hex:
        out["plmn_hex"] = plmn_hex
    if nr_cell_id_int:
        out["nr_cell_id"] = nr_cell_id_int
    return out


def to_sim_control_payload(rc_decoded: dict[str, Any]) -> dict[str, Any] | None:
    """Translate decoded RIC Control Request → sim CU REST payload (OAI 對齊結構).

    sim CU /CU/E2/Control/request 期望（K1/L3 既有實作）：
      {
        ric_req_id: {requestor_id, instance_id},
        ran_function_id: int,
        control_header: {
          control_style: int, control_action_id: int,
          ngap_id, f1ap_id, cell_id  # 視 style 而定
        },
        control_message: { ...style-specific... }
      }

    對應 spec：
      - Style 3 / Action 1 → control_handover    (CCO, ES)
      - Style 2 / Action 6 → control_slice_level_prb_quota  (IM, ES)
    """
    style = rc_decoded.get("style_type", 0)
    action = rc_decoded.get("action_id", 0)
    ueid = rc_decoded.get("ueid", {})
    params = rc_decoded.get("ran_params", {})
    ric_req_id = rc_decoded.get("ric_req_id", {})
    ran_func_id = rc_decoded.get("ran_function_id", 0)

    # sim CU 期望 control_header 有 cell_id 或 node (gNB-CU meid)
    # PRB quota 用 node = sim 自身的 ranName（cell-level 沒給就套到該 gNB 全部 cells）
    # node 從 sim CU 端 default config 取
    node_meid = rc_decoded.get("_node_hint", "")
    base = {
        "ric_req_id": ric_req_id,
        "ran_function_id": ran_func_id,
        "control_header": {
            "control_style": style,
            "control_action_id": action,
            "ngap_id": ueid.get("amf_ue_ngap_id", 0),
            "f1ap_id": ueid.get("gnb_cu_ue_f1ap_id", 0),
            "node": node_meid,
        },
    }

    if style == 3 and action == 1 and ueid.get("kind") == "group":
        # UE Group 換手(v10 第 5 題)—— ControlHeader Format 3。
        # 群組=條件式,由 CU 解析符合的 UE;整條路徑不出現任何 per-UE 識別(L1)。
        def _cond(pid):
            for c in ueid.get("conditions", []):
                if c.get("ranParameter_id") == pid:
                    v = c.get("value")
                    # 解包 pycrate value 容器(第十八輪 5b-2 根因之一:原樣 dict 直傳 CU)
                    if isinstance(v, dict):
                        t, inner = v.get("_type"), v.get("value")
                        if t == "valueOctS" and isinstance(inner, str):
                            try:
                                return bytes.fromhex(inner).decode("utf-8", "replace")
                            except ValueError:
                                return inner
                        if t == "valueInt":
                            return int(inner)
                        v = inner
                    return v.decode() if isinstance(v, (bytes, bytearray)) else v
            return None
        base["action"] = "handover_group"
        base["control_message"] = {
            "ue_group_id": ueid.get("ue_group_id", 0),
            # 10001=NR CGI(來源 cell)、10002=PCI(目標方向)、ARFCN 可選(缺=不限頻率)
            "serving_cell_ncgi": _cond(10001),
            "target_pci": _cond(10002),
            "target_arfcn": _cond(10003),
            # 與逐 UE 3-1 同源抽取 message F1 的 target CGI(第十八輪 5b-2 根因之二:
            # 原樣 ran_params CU 解不動)→ {plmn_hex, nr_cell_id}
            "target_cgi_msg": _extract_target_cgi(params),
        }
        return base

    if style == 9 and action == 1:
        # CONTROL Style 9 / Action 1 — MeasConfig ReportCGI(PCI+ARFCN → 全域 NCGI 解析)。
        # ranP[1]=physicalCellId, ranP[2]=arfcn, ranP[3]=rat(選配)。CGI 由 sim 回 control-ACK outcome。
        def _int_of(pid: int):
            pv = params.get(pid)
            if isinstance(pv, dict):
                pv = pv.get("value", pv)
            try:
                return int(pv)
            except (TypeError, ValueError):
                return None
        pci = _int_of(1)
        arfcn = _int_of(2)
        rat = params.get(3) or "NR"
        logger.info("ReportCGI control decode: pci=%s arfcn=%s rat=%s", pci, arfcn, rat)
        base["action"] = "control_reportcgi"
        base["control_message"] = {"pci": pci, "arfcn": arfcn, "rat": rat}
        return base

    if style == 3 and action == 1:
        # Handover (CCO/ES) — E2SM-RC v01.03 §8.4.5.1 Target Primary Cell ID
        # ranP[1] = Target Primary Cell ID (Structure):
        #   sub-ranP[1] = Choice CGI Id → Structure:
        #     sub-sub-ranP[1] = pLMNIdentity (octS, 3 bytes)
        #     sub-sub-ranP[2] = NRCellIdentity (bitS, 36 bits)
        # rc-probe 簡化版直接送 ranP[1]=structure{ranP[1]=PLMN(octS), ranP[2]=NRCellIdentity(bitS)}
        target_cgi: dict[str, Any] = {}
        plmn_hex = ""
        nr_cell_id_int = 0

        def _walk_for_target_cgi(node: Any) -> None:
            nonlocal plmn_hex, nr_cell_id_int
            if not isinstance(node, dict):
                return
            t = node.get("_type")
            if t == "valueOctS" and not plmn_hex:
                v = node.get("value")
                if isinstance(v, str) and len(v) == 6:  # 3 bytes hex
                    plmn_hex = v
            elif t == "valueBitS" and not nr_cell_id_int:
                v = node.get("value")
                if isinstance(v, dict) and v.get("bits") in (36, 28):
                    nr_cell_id_int = int(v.get("int", 0))
            elif t == "structure":
                for child in (node.get("fields") or {}).values():
                    _walk_for_target_cgi(child)
            elif t == "list":
                for item in node.get("items") or []:
                    for child in (item.get("fields") or {}).values():
                        _walk_for_target_cgi(child)

        # Target Primary Cell ID 依 spec 在 ranParameter-ID=1 的 Structure{PLMN, NRCellId}，
        # 但有些 RIC 放別的編號/格式。先用 structure-based walk 掃所有 ranP。
        for _pv in params.values():
            _walk_for_target_cgi(_pv)

        # Fallback: 實測本場 rc-probe 把 Target Cell 包成單一 valueOctS(ranP id=3)=
        # [1B tag]+PLMN(3B)+NRCellIdentity(36-bit, 5B 左對齊)。取末 8 bytes 當 NR-CGI 解。
        if not (plmn_hex and nr_cell_id_int):
            for _pv in params.values():
                if isinstance(_pv, dict) and _pv.get("_type") == "valueOctS":
                    h = _pv.get("value") or ""
                    if isinstance(h, str) and len(h) >= 16:   # >= 8 bytes
                        cgi = bytes.fromhex(h)[-8:]            # 末 8 bytes = NR-CGI
                        plmn_hex = plmn_hex or cgi[0:3].hex()
                        nr_cell_id_int = nr_cell_id_int or (int.from_bytes(cgi[3:8], "big") >> 4)
                        break

        if plmn_hex:
            target_cgi["plmn_hex"] = plmn_hex
        if nr_cell_id_int:
            target_cgi["nr_cell_id"] = nr_cell_id_int
        logger.info("HO control decode: ranP ids=%s -> plmn=%s nr_cell_id=%s",
                    sorted(params.keys()), plmn_hex or "-", nr_cell_id_int or "-")

        base["action"] = "control_handover"
        base["control_message"] = {"target_cgi": target_cgi}
        return base

    if style == 2 and action == 6:
        # PRB quota (IM/ES) — ranP[1]=min, [2]=max, [3]=dedicated（按 wrapper 慣例）
        numeric_vals: list[int] = []
        for pid in sorted(params.keys()):
            pv = params[pid]
            if isinstance(pv, dict) and pv.get("_type") == "valueInt":
                numeric_vals.append(int(pv.get("value", 0)))
        min_prb = numeric_vals[0] if len(numeric_vals) > 0 else 0
        max_prb = numeric_vals[1] if len(numeric_vals) > 1 else 100
        dedicated_prb = numeric_vals[2] if len(numeric_vals) > 2 else 100
        base["action"] = "control_slice_level_prb_quota"
        base["control_message"] = {
            "min_prb": min_prb,
            "max_prb": max_prb,
            "dedicated_prb": dedicated_prb,
            "_raw_ran_params": params,
        }
        return base

    logger.warning("Unsupported (style=%d, action=%d) — no sim payload mapping", style, action)
    return None


# ── Encoder: RIC_CONTROL_ACK ─────────────────────────────────────

# E2AP procedureCode for RICcontrol = 4
_PROC_CODE_RICcontrol = 4
_IE_ID_RICrequestID = 29
_IE_ID_RANfunctionID = 5
_IE_ID_RICcallProcessID = 20
_IE_ID_RICcontrolOutcome = 32


def encode_ric_control_ack(
    ric_req_id: dict[str, int],
    ran_function_id: int,
    call_process_id: bytes = b"",
    outcome_bytes: bytes = b"",
) -> bytes:
    """Encode RIC Control Acknowledge (successful) → APER E2AP-PDU bytes.

    Per E2AP §9.2.4：
      protocolIEs:
        id=29 RICrequestID    (echo)
        id=5  RANfunctionID    (echo)
        id=20 RICcallProcessID (optional, echo if present)
        id=32 RICcontrolOutcome (OCTET STRING — E2SM-RC ControlOutcome PER bytes)
    """
    rt = _load_runtime()
    pdu_cls = rt.E2AP_PDU_Descriptions.E2AP_PDU

    ies = [
        {"id": _IE_ID_RICrequestID, "criticality": "reject",
         "value": ("RICrequestID", {
             "ricRequestorID": ric_req_id.get("requestor_id", 0),
             "ricInstanceID": ric_req_id.get("instance_id", 0),
         })},
        {"id": _IE_ID_RANfunctionID, "criticality": "reject",
         "value": ("RANfunctionID", ran_function_id)},
    ]
    if call_process_id:
        ies.append({"id": _IE_ID_RICcallProcessID, "criticality": "reject",
                    "value": ("RICcallProcessID", call_process_id)})
    if outcome_bytes:
        ies.append({"id": _IE_ID_RICcontrolOutcome, "criticality": "reject",
                    "value": ("RICcontrolOutcome", outcome_bytes)})

    ack = {"protocolIEs": ies}

    pdu_cls.set_val(("successfulOutcome", {
        "procedureCode": _PROC_CODE_RICcontrol,
        "criticality": "reject",
        "value": ("RICcontrolAcknowledge", ack),
    }))
    return pdu_cls.to_aper()


# ── Encoder: RIC_CONTROL_FAILURE ─────────────────────────────────

_IE_ID_Cause = 1


def encode_ric_control_failure(
    ric_req_id: dict[str, int],
    ran_function_id: int,
    cause: tuple[str, str],
    call_process_id: bytes = b"",
) -> bytes:
    """Encode RIC Control Failure (unsuccessfulOutcome) → APER E2AP-PDU bytes.

    cause = (group, value) e.g. ("ricRequest", "ran-function-id-invalid"),
    ("ricRequest", "action-not-supported"), ("ricRequest", "control-message-invalid").

    Per E2AP §9.2.5：
      protocolIEs:
        id=29 RICrequestID    (echo)
        id=5  RANfunctionID   (echo)
        id=20 RICcallProcessID (optional, echo if present)
        id=1  Cause
    """
    rt = _load_runtime()
    pdu_cls = rt.E2AP_PDU_Descriptions.E2AP_PDU

    ies: list[dict[str, Any]] = [
        {"id": _IE_ID_RICrequestID, "criticality": "reject",
         "value": ("RICrequestID", {
             "ricRequestorID": ric_req_id.get("requestor_id", 0),
             "ricInstanceID": ric_req_id.get("instance_id", 0),
         })},
        {"id": _IE_ID_RANfunctionID, "criticality": "reject",
         "value": ("RANfunctionID", ran_function_id)},
    ]
    if call_process_id:
        ies.append({"id": _IE_ID_RICcallProcessID, "criticality": "reject",
                    "value": ("RICcallProcessID", call_process_id)})
    ies.append({"id": _IE_ID_Cause, "criticality": "ignore",
                "value": ("Cause", cause)})

    pdu_cls.set_val(("unsuccessfulOutcome", {
        "procedureCode": _PROC_CODE_RICcontrol,
        "criticality": "reject",
        "value": ("RICcontrolFailure", {"protocolIEs": ies}),
    }))
    return pdu_cls.to_aper()


# ── Encoder: RANfunction-Description ─────────────────────────────

def encode_rc_ran_function_description() -> bytes:
    """Encode E2SM-RC-RANFunctionDefinition (v01.03 §8.2.1) → APER bytes.

    對齊 RIC team rc-probe (`/home/mitlab/xapps/rc-probe/`) — only Control list,
    no EventTrigger / Report / Insert / Policy.

    Declared Control Styles:
      Style 2 / Action 6: Slice-level PRB Quota (RANParam 1=min, 2=max, 3=dedicated)
      Style 3 / Action 1: Handover Control (RANParam 1=Target Primary Cell ID)
        — sim 端可接, RIC rc-probe 尚未實作 sender (STYLE3_ACTION1_HDR=b"")
    """
    rfd_cls = _rc_ies().E2SM_RC_RANFunctionDefinition

    style_2_6 = {
        "ric-ControlStyle-Type": 2,
        "ric-ControlStyle-Name": "Slice-level PRB Quota",
        "ric-ControlAction-List": [{
            "ric-ControlAction-ID": 6,
            "ric-ControlAction-Name": "Slice-level PRB Quota",
            "ran-ControlActionParameters-List": [
                {"ranParameter-ID": 1, "ranParameter-name": "Min PRB Ratio"},
                {"ranParameter-ID": 2, "ranParameter-name": "Max PRB Ratio"},
                {"ranParameter-ID": 3, "ranParameter-name": "Dedicated PRB Ratio"},
            ],
            # v10 模組中此欄位為**必填**(每個 ControlAction 都要帶,不只 3/1)
            **({"ueGroup-ControlAction-Supported": "false"} if _rc_v10_enabled() else {}),
        }],
        "ric-ControlHeaderFormat-Type": 1,
        "ric-ControlMessageFormat-Type": 1,
        "ric-ControlOutcomeFormat-Type": 1,
    }
    style_3_1 = {
        "ric-ControlStyle-Type": 3,
        "ric-ControlStyle-Name": "Connected Mode Mobility Control",
        "ric-ControlAction-List": [{
            "ric-ControlAction-ID": 1,
            "ric-ControlAction-Name": "Handover Control",
            # v01.03 沒有 ueGroup 欄位,硬加會整個 RFD 編碼失敗退回 empty stub
            # (2026-08-25 實測)—— 只在 v10 模組下宣告。
            **({"ueGroup-ControlAction-Supported": "true"} if _rc_v10_enabled() else {}),
            "ran-ControlActionParameters-List": [
                {"ranParameter-ID": 1, "ranParameter-name": "Target Primary Cell ID",
                 # 宣告「群組控制用 Header Format 3 + Message Format 1」——
                 # rc-probe 從 E2 Setup 讀出該用哪組 format,不必寫死假設。
                 **({"listOfAdditionalSupportedFormats-UEGroupControl": [
                     {"ric-ControlHeaderFormat-Type": 3,
                      "ric-ControlMessageFormat-Type": 1}]} if _rc_v10_enabled() else {})},
            ],
        }],
        # Format 1 = 逐 UE;Format 3 = 群組(ue-Group-Definition 條件式)
        "ric-ControlHeaderFormat-Type": 1,
        "ric-ControlMessageFormat-Type": 1,
        "ric-ControlOutcomeFormat-Type": 1,
    }

    rfd_value = {
        "ranFunction-Name": {
            "ranFunction-ShortName": "ORAN-E2SM-RC",
            "ranFunction-E2SM-OID": "1.3.6.1.4.1.53148.1.1.2.3",
            "ranFunction-Description": "RC",
            "ranFunction-Instance": 0,
        },
        "ranFunctionDefinition-Control": {
            "ric-ControlStyle-List": [style_2_6, style_3_1],
        },
    }

    rfd_cls.set_val(rfd_value)
    return rfd_cls.to_aper()


def selftest_rc_control_round_trip() -> dict[str, Any]:
    """Build a fake Style 2 Action 6 RIC_CONTROL_REQ + decode → sim payload."""
    rt = _load_runtime()
    pdu_cls = rt.E2AP_PDU_Descriptions.E2AP_PDU
    ch_cls = rt.E2SM_RC_IEs.E2SM_RC_ControlHeader
    cm_cls = rt.E2SM_RC_IEs.E2SM_RC_ControlMessage

    # Build header: Style 2 / Action 6 / no specific UE (use any UEID)
    ch_cls.set_val({
        "ric-controlHeader-formats": ("controlHeader-Format1", {
            "ueID": ("gNB-UEID", {
                "amf-UE-NGAP-ID": 1,
                "guami": {
                    "pLMNIdentity": bytes.fromhex("02f859"),
                    "aMFRegionID": (1, 8),
                    "aMFSetID": (1, 10),
                    "aMFPointer": (0, 6),
                },
                "gNB-CU-UE-F1AP-ID-List": [{"gNB-CU-UE-F1AP-ID": 1}],
            }),
            "ric-Style-Type": 2,
            "ric-ControlAction-ID": 6,
            "ric-ControlDecision": "accept",
        }),
    })
    header_bytes = ch_cls.to_aper()

    # Build message: ranP-List with 3 items: min=10, max=50, dedicated=100
    cm_cls.set_val({
        "ric-controlMessage-formats": ("controlMessage-Format1", {
            "ranP-List": [
                {"ranParameter-ID": 1, "ranParameter-valueType": (
                    "ranP-Choice-ElementTrue",
                    {"ranParameter-value": ("valueInt", 10)})},
                {"ranParameter-ID": 2, "ranParameter-valueType": (
                    "ranP-Choice-ElementTrue",
                    {"ranParameter-value": ("valueInt", 50)})},
                {"ranParameter-ID": 3, "ranParameter-valueType": (
                    "ranP-Choice-ElementTrue",
                    {"ranParameter-value": ("valueInt", 100)})},
            ],
        }),
    })
    message_bytes = cm_cls.to_aper()

    # Build full RIC_CONTROL_REQ
    pdu_cls.set_val(("initiatingMessage", {
        "procedureCode": 4,    # ricControl
        "criticality": "reject",
        "value": ("RICcontrolRequest", {
            "protocolIEs": [
                {"id": 29, "criticality": "reject",
                 "value": ("RICrequestID", {"ricRequestorID": 5, "ricInstanceID": 7})},
                {"id": 5, "criticality": "reject",
                 "value": ("RANfunctionID", 3)},  # RC ran_function_id
                {"id": 22, "criticality": "reject",
                 "value": ("RICcontrolHeader", header_bytes)},
                {"id": 23, "criticality": "reject",
                 "value": ("RICcontrolMessage", message_bytes)},
            ],
        }),
    }))
    raw = pdu_cls.to_aper()

    decoded = decode_ric_control_request(raw)
    sim_payload = to_sim_control_payload(decoded)
    ack = encode_ric_control_ack(decoded["ric_req_id"], decoded["ran_function_id"])

    return {
        "encoded_size": len(raw),
        "decoded": decoded,
        "sim_payload": sim_payload,
        "ack_size": len(ack),
    }
