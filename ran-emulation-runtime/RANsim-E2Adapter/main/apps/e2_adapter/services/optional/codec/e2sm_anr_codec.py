"""E2SM-ANR codec — gNB SON 觸發函式(ANR 情境 v8,自定 E2SM)。

定位(ANR情境_v8.docx §貳C):xApp 由組態書寫者 → gNB SON 觸發者。現行 WG3 規格無
「觸發 gNB SON」之訊息(RC 十式樣無、CCC 無),故屬自定 E2SM 承載。OID 取 vendor 空間
1.3.6.1.4.1.53148.1.1.2.6,RAN function ID 預設 6。

★ 與 CCC 相同:Control Header / Message 是 **JSON**(非 ASN.1)。E2AP 外層照 RC/CCC 解,
  內層 json.loads。

Control Header (JSON): { "controlHeaderFormat": { "ricStyleType": 1 } }
Control Message (JSON):
  { "controlMessageFormat": { "sonTriggerRequest": {
      "requestType": "ADD" | "REMOVE" | "FLAG",
      "sourceCellId": "cg0_c0",
      "target": { "cgi", "pci", "arfcn", "rat"?, "plmn"? },   // ADD 用
      "targetCgi": "...",                                       // REMOVE / FLAG 用
      "reason": "...",                                          // REMOVE 用
      "flag": "hoBlocklist"|"noRemove"|"xnBlocklist",           // FLAG 用
      "op": "set"|"clear"                                       // FLAG 用
  } } }

對應 xApp 命令:
  SONTRIG_ANR_ADD_REQUEST(cellId, {cgi,pci,arfcn[,rat,plmn]})   → requestType=ADD
  SONTRIG_ANR_REMOVE_REQUEST(cellId, targetCgi, reason)         → requestType=REMOVE
  SONTRIG_ANR_FLAG_REQUEST(cellId, targetCgi, flag, set|clear)  → requestType=FLAG
"""
from __future__ import annotations

import json
from typing import Any

from main.apps.e2_adapter.services.optional.codec.e2ap_codec import _load_runtime
from main.utils.logger import get_logger

logger = get_logger(__name__)

ANR_RAN_FUNCTION_ID = 6
ANR_OID = "1.3.6.1.4.1.53148.1.1.2.6"
ANR_RIC_STYLE_TYPE = 1  # SON Trigger (NR Cell Relation control)

_VALID_REQ_TYPES = ("ADD", "REMOVE", "FLAG")
_VALID_FLAGS = ("hoBlocklist", "noRemove", "xnBlocklist")


def decode_ric_control_request(data: bytes) -> dict[str, Any]:
    """Decode RIC Control Request(ANR SON 觸發)→ dict。
    Returns:
      { ric_req_id, ran_function_id, ric_style_type, request:{...}|None,
        raw_header_bytes, raw_message_bytes }
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

    IE_RICrequestID = 29
    IE_RANfunctionID = 5
    IE_RICcontrolHeader = 22
    IE_RICcontrolMessage = 23

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

    ric_style_type = 0
    try:
        hdr = json.loads(header_bytes.decode("utf-8")) if header_bytes else {}
        ric_style_type = int(hdr.get("controlHeaderFormat", {}).get("ricStyleType", 0))
    except Exception as exc:  # noqa: BLE001
        logger.warning("ANR control header JSON decode failed: %s", exc)

    request: dict[str, Any] | None = None
    try:
        msg = json.loads(message_bytes.decode("utf-8")) if message_bytes else {}
        req = msg.get("controlMessageFormat", {}).get("sonTriggerRequest")
        request = _normalize_request(req) if req else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("ANR control message JSON decode failed: %s", exc)

    return {
        "ric_req_id": ric_req_id,
        "ran_function_id": ran_function_id,
        "ric_style_type": ric_style_type,
        "request": request,
        "raw_header_bytes": len(header_bytes),
        "raw_message_bytes": len(message_bytes),
    }


def _normalize_request(req: dict[str, Any]) -> dict[str, Any] | None:
    """驗證 + 正規化單筆 SON 觸發請求;無效回 None。"""
    rtype = str(req.get("requestType", "")).upper()
    if rtype not in _VALID_REQ_TYPES:
        logger.warning("ANR: unknown requestType %r", req.get("requestType"))
        return None
    src = req.get("sourceCellId")
    if not src:
        logger.warning("ANR: sourceCellId required")
        return None

    out: dict[str, Any] = {"requestType": rtype, "sourceCellId": src}

    if rtype == "ADD":
        tgt = req.get("target") or {}
        if not tgt.get("cgi"):
            logger.warning("ANR ADD: target.cgi required")
            return None
        out["target"] = {
            "cgi": tgt.get("cgi"),
            "pci": tgt.get("pci"),
            "arfcn": tgt.get("arfcn"),
            "rat": tgt.get("rat", "NR"),
            "plmn": tgt.get("plmn", ""),
        }
    elif rtype == "REMOVE":
        if not req.get("targetCgi"):
            logger.warning("ANR REMOVE: targetCgi required")
            return None
        out["targetCgi"] = req.get("targetCgi")
        out["reason"] = req.get("reason", "")
    elif rtype == "FLAG":
        flag = req.get("flag")
        op = str(req.get("op", "")).lower()
        if not req.get("targetCgi") or flag not in _VALID_FLAGS or op not in ("set", "clear"):
            logger.warning("ANR FLAG: need targetCgi + flag∈%s + op∈{set,clear}", _VALID_FLAGS)
            return None
        out["targetCgi"] = req.get("targetCgi")
        out["flag"] = flag
        out["op"] = op

    return out


def to_sim_control_payload(anr_decoded: dict[str, Any]) -> dict[str, Any] | None:
    """ANR decoded → sim CU /CU/E2/Anr/control payload。"""
    req = anr_decoded.get("request")
    if not req:
        return None
    return {
        "ric_req_id": anr_decoded.get("ric_req_id", {}),
        "ran_function_id": anr_decoded.get("ran_function_id", ANR_RAN_FUNCTION_ID),
        "sim_action": "anr_son_trigger",
        "request": req,
    }


def encode_anr_ran_function_description() -> bytes:
    """ANR RAN Function Definition(JSON)— E2 Setup 廣播用。宣告 SON 觸發能力。"""
    rfd = {
        "ranFunctionName": {
            "ranFunctionShortName": "DT-E2SM-ANR",
            "ranFunctionServiceModelOID": ANR_OID,
            "ranFunctionDescription": "gNB SON trigger (ANR NR Cell Relation add/remove/flag)",
        },
        "listOfSupportedRICControlStyles": [
            {"ricStyleType": ANR_RIC_STYLE_TYPE, "ricStyleName": "SON Trigger",
             "listOfSupportedControlActions": [
                 {"controlActionName": "ADD_REQUEST"},
                 {"controlActionName": "REMOVE_REQUEST"},
                 {"controlActionName": "FLAG_REQUEST"},
             ]},
        ],
    }
    return json.dumps(rfd, separators=(",", ":")).encode("utf-8")


# ── ANR Indication(sim → RIC 觀測資料;JSON payload,比照 FULLKPM)──────
# 2026-08-12:E2SM-ANR 加 indication 方向 —— xApp 訂 func 6 後每 period 收到
# ANR情境_v8 卷面觀測資料(e2NodeInformation + kpmIndication + RLF/MRO + 量測聚合)。
# payload zlib 壓縮(可能大),對齊 FULLKPM 的信封:header 帶 encoding/part/parts。

def encode_indication_header(timestamp_ms: int, sn: int, *,
                             part: int = 0, parts: int = 1, raw_bytes: int = 0) -> bytes:
    return json.dumps(
        {"timestamp_ms": int(timestamp_ms), "sn": int(sn), "format": "DT-ANR-v1",
         "encoding": "zlib", "part": int(part), "parts": int(parts),
         "raw_bytes": int(raw_bytes)},
        separators=(",", ":"),
    ).encode("utf-8")


def build_indication_payloads(anr_data: dict[str, Any], sn: int,
                              chunk_bytes: int = 6000) -> list:
    """anr_data(CU /E2/Anr/indication 的 data 區)→ [(hdr, msg), ...],zlib+分塊。"""
    import zlib

    raw = json.dumps(anr_data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    comp = zlib.compress(raw, 6)
    ts = int(anr_data.get("timestamp_ms", 0)) if isinstance(anr_data, dict) else 0
    chunks = [comp[i:i + chunk_bytes] for i in range(0, len(comp), chunk_bytes)] or [b""]
    n = len(chunks)
    return [
        (encode_indication_header(ts, sn, part=i, parts=n, raw_bytes=len(raw)), chunk)
        for i, chunk in enumerate(chunks)
    ]


def selftest_anr_decode() -> dict[str, Any]:
    """回歸自測:三種請求的正規化。"""
    add = _normalize_request({"requestType": "ADD", "sourceCellId": "cg0_c0",
                              "target": {"cgi": "cg1_c0", "pci": 2, "arfcn": 633333}})
    rem = _normalize_request({"requestType": "REMOVE", "sourceCellId": "cg0_c0",
                              "targetCgi": "cg1_c0", "reason": "aging"})
    flag = _normalize_request({"requestType": "FLAG", "sourceCellId": "cg0_c0",
                               "targetCgi": "cg1_c0", "flag": "hoBlocklist", "op": "set"})
    bad = _normalize_request({"requestType": "NOPE", "sourceCellId": "x"})
    return {"add": add, "remove": rem, "flag": flag, "bad_is_none": bad is None}
