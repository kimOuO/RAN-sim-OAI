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
from main.apps.e2_adapter.services.optional.codec.e2sm_fullkpm_codec import OID_ROOT as _OID_ROOT
from main.apps.e2_adapter.services.optional.codec.e2sm_fullkpm_codec import V2_EVENT_TRIGGER_STYLE as _V2_ET
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
    IE_RICcallProcessID = 20
    call_process_id = b""

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
            # RIC 閘道的對帳標籤(<sid>|<node>|g<gen>|<label>,UTF-8)放這裡;ACK / Failure 原樣帶回
            call_process_id = bytes(val) if not isinstance(val, bytes) else val

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
        "call_process_id": call_process_id,
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


# ── v2(func 8):OID 與分塊合規版 ────────────────────────────
# v1(func 6)與 FULLKPM v1 同樣的兩個問題:OID 落在 O-RAN 聯盟企業號(53148)下;
# 一份觀測壓縮後切塊散在多則 indication,單則無法獨立解讀。另外 v1 的 RAN Function
# Definition 只宣告 control,沒有宣告它實際提供的兩種 indication。
# v2:
#   1. OID 用 UUID 弧(與 FULLKPM v2 同根):<root>.1.2。
#   2. 週期觀測(action 0):每個 serving cell 一則自足報告(該 cell 的組態、以它為 source 的
#      鄰區關係 / 變更事件 / 旗標事件、cell 級 KPM、逐關係 KPM、該 cell 的 NRT 用量)
#      + 一則 node 報告(頻率關係、NRT 上限與總表、量測聚合、CGI 取樣、CCC 事件,
#      以及 source 不在 serving cell 清單裡的殘留條目 —— 一筆都不丟)。
#   3. 關係變更(action 2,事件驅動):每個有變更的 source cell 一則自足報告(該 cell 完整關係表 + 變更標示)。
#   4. 單則壓縮後超過上限時依清單分頁;第一頁帶完整非清單欄位,後續頁帶識別欄位與該頁條目。
#   v1(func 6)保持不變,RIC 端 dt-anr 改好後再移除。

ANR_V2_RAN_FUNCTION_ID = 8
ANR_V2_OID = f"{_OID_ROOT}.1.2"
ANR_V2_FORMAT = "DT-ANR-v2"
_ANR_V2_MSG_LIMIT = 6000
_TOP = ("timestamp", "sceneSimMs", "granularityPeriod")


def encode_anr_v2_ran_function_description() -> bytes:
    rfd = {
        "ranFunctionName": {
            "ranFunctionShortName": "DT-E2SM-ANR",
            "ranFunctionServiceModelOID": ANR_V2_OID,
            "ranFunctionDescription": (
                "gNB ANR observation and SON trigger. Indications are self-contained: "
                "one report per serving cell plus one node report per period."
            ),
            "ranFunctionInstance": 0,
        },
        "listOfSupportedEventTriggerStyles": [_V2_ET],
        "listOfSupportedReportStyles": [
            {"ricReportStyleType": 1, "ricReportStyleName": "Periodic ANR Observation", "ricActionId": 0,
             "ricEventTriggerStyleType": 1,
             "indicationHeaderFormat": "JSON {format, timestamp, timestamp_ms, sceneSimMs, sn, action, report, cell, report_index, report_count, page, pages}",
             "indicationMessageFormat": "zlib-compressed UTF-8 JSON, one self-contained report",
             "maxIndicationMessageBytes": _ANR_V2_MSG_LIMIT},
            {"ricReportStyleType": 2, "ricReportStyleName": "Neighbour Relation Change", "ricActionId": 2,
             "ricEventTriggerStyleType": 1,   # reportingPeriodMs = 變更偵測的輪詢間隔
             "indicationHeaderFormat": "same as style 1",
             "indicationMessageFormat": "zlib-compressed UTF-8 JSON: one changed source cell's full relation table + change marks",
             "maxIndicationMessageBytes": _ANR_V2_MSG_LIMIT},
        ],
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


def _ts_ms(iso: Any) -> int:
    """v10 的 timestamp 是 ISO 字串(v1 header 讀不存在的 timestamp_ms → 一律 0);v2 header 換算成毫秒。"""
    from datetime import datetime
    try:
        return int(datetime.fromisoformat(str(iso)).timestamp() * 1000)
    except (TypeError, ValueError):
        return 0


def _split_anr_reports(data: dict[str, Any]) -> list[tuple[dict, dict]]:
    """v10 全量觀測 → [(header 欄位, 報告內容)]:每 serving cell 一份 + node 一份。"""
    top = {k: data[k] for k in _TOP if k in data}
    ni = data.get("e2NodeInformation") or {}
    kpm = data.get("kpmIndication") or {}
    serving = list(ni.get("servingCells") or [])
    ids = [c.get("ncgi") for c in serving]
    by_src = lambda items: {i: [x for x in items or [] if x.get("sourceCellNcgi") == i] for i in ids}  # noqa: E731
    rels, chg, flg = by_src(ni.get("neighbourCellRelations")), by_src(ni.get("relationChangeEvents")), by_src(ni.get("flagChangeEvents"))
    pnr = by_src(kpm.get("perNeighbourRelation"))
    cl = kpm.get("cellLevel") or {}
    cap = ni.get("nrtCapacity") or {}
    claimed_cl: set[str] = set()
    out: list[tuple[dict, dict]] = []
    for c in serving:
        n = c.get("ncgi")
        mine = {k: v for k, v in cl.items() if k.endswith(f".{n}")}
        claimed_cl.update(mine)
        out.append(({"report": "cell", "cell": n}, {
            **top,
            "e2NodeInformation": {
                "servingCells": [c],
                "neighbourCellRelations": rels[n],
                "nrtCapacity": {"limit": cap.get("limit"), "used": (cap.get("usedByCell") or {}).get(n, 0)},
                "relationChangeEvents": chg[n],
                "flagChangeEvents": flg[n],
            },
            "kpmIndication": {"cellLevel": mine, "perNeighbourRelation": pnr[n]},
        }))
    rest = lambda items: [x for x in items or [] if x.get("sourceCellNcgi") not in ids]  # noqa: E731
    out.append(({"report": "node"}, {
        **top,
        "cells": [{"ncgi": c.get("ncgi"), "physicalCellId": c.get("physicalCellId"), "arfcn": c.get("arfcn")} for c in serving],
        "e2NodeInformation": {
            "frequencyRelations": ni.get("frequencyRelations") or [],
            "nrtCapacity": cap,
            "anrIntraEnabled": ni.get("anrIntraEnabled"),
            # source 不在 serving cell 清單的殘留條目(例如換劇本後的舊 cell)放這裡,不丟
            "neighbourCellRelations": rest(ni.get("neighbourCellRelations")),
            "relationChangeEvents": rest(ni.get("relationChangeEvents")),
            "flagChangeEvents": rest(ni.get("flagChangeEvents")),
        },
        "kpmIndication": {"cellLevel": {k: v for k, v in cl.items() if k not in claimed_cl},
                          "perNeighbourRelation": rest(kpm.get("perNeighbourRelation"))},
        "e2MessageCopyAggregate": data.get("e2MessageCopyAggregate") or {},
        "cgiResolutionSampling": data.get("cgiResolutionSampling") or [],
        "cccConfigurationEvents": data.get("cccConfigurationEvents") or [],
    }))
    return out


def _zc(obj: Any) -> bytes:
    import zlib
    return zlib.compress(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), 6)


def _list_paths(body: dict, prefix: tuple = ()) -> list[tuple]:
    """body 裡所有 list 欄位的路徑(分頁對象)。"""
    out = []
    for k, v in body.items():
        if isinstance(v, list) and v:
            out.append((*prefix, k))
        elif isinstance(v, dict):
            out.extend(_list_paths(v, (*prefix, k)))
    return out


def _get(d: dict, path: tuple) -> Any:
    for k in path:
        d = d[k]
    return d


def _with(d: dict, path: tuple, value: Any) -> dict:
    """回傳把 path 設成 value 的淺層複本(只複製路徑上的 dict)。"""
    if len(path) == 1:
        return {**d, path[0]: value}
    return {**d, path[0]: _with(d.get(path[0]) or {}, path[1:], value)}


def _paginate_anr(body: dict, limit: int, ident_keys: tuple) -> list[bytes]:
    """壓縮後超過上限 → 所有清單欄位同步切成 n 段;第 0 頁帶完整非清單欄位,其餘頁帶識別欄位 + 各清單該段。"""
    whole = _zc(body)
    paths = _list_paths(body)
    if len(whole) <= limit or not paths:
        return [whole]
    longest = max(len(_get(body, p)) for p in paths)
    ident = {k: body[k] for k in ident_keys if k in body}
    for n in range(2, longest + 1):
        pages = []
        for i in range(n):
            page = body if i == 0 else ident
            for p in paths:
                items = _get(body, p)
                size = -(-len(items) // n)
                page = _with(page, p, items[i * size:(i + 1) * size])
            pages.append(_zc(page))
        if all(len(x) <= limit for x in pages):
            return pages
    return pages   # 單一條目仍超過上限:不再切,照送(不靜默丟資料)


def _headers(items: list[tuple[dict, bytes, int, int]], data: dict, sn: int, action: int) -> list[tuple[bytes, bytes]]:
    base = {"format": ANR_V2_FORMAT, "timestamp": data.get("timestamp"), "timestamp_ms": _ts_ms(data.get("timestamp")),
            "sceneSimMs": data.get("sceneSimMs"), "sn": int(sn), "action": action}
    total = len(items)
    return [(json.dumps({**base, **hdr, "encoding": "zlib", "report_index": i, "report_count": total,
                         "page": p, "pages": np}, separators=(",", ":")).encode("utf-8"), msg)
            for i, (hdr, msg, p, np) in enumerate(items)]


def build_anr_v2_payloads(data: dict[str, Any], sn: int, limit: int = _ANR_V2_MSG_LIMIT) -> list[tuple[bytes, bytes]]:
    """action 0 週期觀測:v10 全量 → 每則自足的 [(header, message)]。"""
    items = []
    for hdr, body in _split_anr_reports(data):
        pages = _paginate_anr(body, limit, (*_TOP, "cells"))
        items += [(hdr, m, p, len(pages)) for p, m in enumerate(pages)]
    return _headers(items, data, sn, 0)


def relation_versions(data: dict[str, Any]) -> dict[tuple, Any]:
    rels = (data.get("e2NodeInformation") or {}).get("neighbourCellRelations") or []
    return {(r.get("sourceCellNcgi"), r.get("targetCellGlobalId")): r.get("version") for r in rels}


def build_anr_v2_change_payloads(data: dict[str, Any], prev: dict[tuple, Any], sn: int,
                                 limit: int = _ANR_V2_MSG_LIMIT) -> list[tuple[bytes, bytes]]:
    """action 2 關係變更:與上一輪的 (source, target) → version 比,每個有變更的 source cell 送一則自足報告
    (該 cell 目前完整關係表 + 新增 / 移除 / 版本變動標示)。沒有變更回空清單。"""
    cur = relation_versions(data)
    rels = (data.get("e2NodeInformation") or {}).get("neighbourCellRelations") or []
    changed = sorted({k[0] for k in set(cur) ^ set(prev)} | {k[0] for k in cur if k in prev and cur[k] != prev[k]},
                     key=lambda x: str(x))
    top = {k: data[k] for k in _TOP if k in data}
    items = []
    for src in changed:
        marks = {"added": [f"{a}->{b}" for a, b in cur if a == src and (a, b) not in prev],
                 "removed": [f"{a}->{b}" for a, b in prev if a == src and (a, b) not in cur],
                 "versionBumped": [f"{a}->{b}" for a, b in cur if a == src and (a, b) in prev and cur[(a, b)] != prev[(a, b)]]}
        body = {**top, "sourceCellNcgi": src,
                "e2NodeInformation": {"neighbourCellRelations": [r for r in rels if r.get("sourceCellNcgi") == src]},
                "changeMarks": marks}
        pages = _paginate_anr(body, limit, (*_TOP, "sourceCellNcgi"))
        items += [({"report": "change", "cell": src}, m, p, len(pages)) for p, m in enumerate(pages)]
    return _headers(items, data, sn, 2)
