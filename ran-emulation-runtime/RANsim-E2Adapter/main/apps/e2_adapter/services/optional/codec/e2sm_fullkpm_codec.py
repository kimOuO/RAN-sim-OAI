"""E2SM-DTFULLKPM codec — DT 完整 KPM(E2_data_example.md 全格式)vendor service model。

設計比照 O-RAN E2SM-CCC 的先例:E2AP 外層照標準 ASN.1(SUB_REQ / SUB_RESP /
RIC_INDICATION),**內層 payload 用 JSON**(RANfunction-Description、Indication
Header、Indication Message 都是 UTF-8 JSON bytes)。

RIC/xApp 端使用方式:
  1. E2 Setup 看到 ran_function_id=5(OID 1.3.6.1.4.1.53148.1.1.2.100)
  2. 對 func 5 發標準 RICsubscriptionRequest(event trigger 建議帶 KPM Format1
     period;解不出來 adapter 預設 1000ms)
  3. 每 period 收 RIC_INDICATION:
     - indicationHeader = JSON {"timestamp_ms", "sn", "format": "DTFULLKPM-v1"}
     - indicationMessage = JSON,結構 = docs/E2_data_example.md 的 data 區
       (timestamp_ms/compute_ms/tick_ms/e2[]/ue_status[]/pm{}/bbu_status/warnings)
"""
from __future__ import annotations

import json
from typing import Any

FULLKPM_RAN_FUNCTION_ID = 5
FULLKPM_OID = "1.3.6.1.4.1.53148.1.1.2.100"
FULLKPM_STYLE_TYPE = 1  # Periodic full-state report


def encode_fullkpm_ran_function_description() -> bytes:
    """RANfunction-Description(JSON,比照 CCC)— E2 Setup 廣播用。"""
    rfd = {
        "ranFunctionName": {
            "ranFunctionShortName": "DT-E2SM-FULLKPM",
            "ranFunctionServiceModelOID": FULLKPM_OID,
            "ranFunctionDescription": (
                "DT full-state KPM report: per-cell/UE radio meas + neighbors + "
                "3GPP TS 28.552 PM counters (190/cell) + BBU status + UE positions. "
                "Indication message = JSON (schema: XAPP_DT docs/E2_data_example.md, "
                "field reference: docs/E2_full_kpm_fields.md)."
            ),
        },
        "listOfSupportedReportStyles": [
            {
                "ricReportStyleType": FULLKPM_STYLE_TYPE,
                "ricReportStyleName": "Periodic Full-State Report (JSON)",
                "eventTriggerFormat": "E2SM-KPM Format1 period (fallback 1000ms)",
                "indicationHeaderFormat": "JSON {timestamp_ms, sn, format}",
                "indicationMessageFormat": "JSON E2_data_example.md data object",
            },
        ],
    }
    return json.dumps(rfd, separators=(",", ":")).encode("utf-8")


# OSC e2term 的 SCTP 接收 buffer 是 8KB(RECEIVE_SCTP_BUFFER_SIZE=8192);
# 整個 E2AP PDU 必須壓在其下,否則 e2term 逐段 recv 逐段 decode fail。
# 61KB JSON zlib 後 ~2.1KB(28x);超大場景才會分塊。6000B 留 outer 頭高裕度。
_CHUNK_BYTES = 6000


def encode_indication_header(timestamp_ms: int, sn: int, *,
                             part: int = 0, parts: int = 1, raw_bytes: int = 0) -> bytes:
    return json.dumps(
        {"timestamp_ms": int(timestamp_ms), "sn": int(sn), "format": "DTFULLKPM-v1",
         "encoding": "zlib", "part": int(part), "parts": int(parts),
         "raw_bytes": int(raw_bytes)},
        separators=(",", ":"),
    ).encode("utf-8")


def build_indication_payloads(full_data: dict[str, Any], sn: int) -> list[tuple[bytes, bytes]]:
    """full_data → [(header_bytes, message_bytes), ...](zlib 壓縮,必要時分塊)。

    xApp 端還原:同 sn 的 parts 依 part 序 concat → zlib.decompress → json.loads。
    多數情況 parts=1。
    """
    import zlib

    raw = json.dumps(full_data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    comp = zlib.compress(raw, 6)
    ts = int(full_data.get("timestamp_ms", 0))
    chunks = [comp[i:i + _CHUNK_BYTES] for i in range(0, len(comp), _CHUNK_BYTES)] or [b""]
    n = len(chunks)
    return [
        (encode_indication_header(ts, sn, part=i, parts=n, raw_bytes=len(raw)), chunk)
        for i, chunk in enumerate(chunks)
    ]


# ── v2(func 7):OID 與分塊合規版 ────────────────────────────
# v1 的兩個問題:
#   1. OID 落在 O-RAN 聯盟的私有企業號(53148)底下 → 不是我們可以分配的空間。
#   2. 一份報告壓縮後切塊分散在多則 RIC_INDICATION,單則無法獨立解讀,
#      不符 E2AP「每則 indication 自成一份報告」的語意。
# v2:
#   1. OID 用 ITU-T X.667 / ISO/IEC 9834-8 的 UUID 弧 2.25.<UUID 整數>,免註冊且全域唯一;
#      其下 .1 = E2SM,.1.1 = 本模型(.1.2 預留給 ANR)。之後若申請到 IANA PEN 可再換。
#   2. 依內容切成自足報告:每 cell 一則(cell 量測 + 服務中 UE + 該 cell PM + 所屬 gNB 的 BBU),
#      外加一則節點報告(未附著 UE、告警)。單 cell 仍超過上限時,依 UE 分頁,每頁仍可獨立解讀。
#      壓縮(zlib)是本模型宣告的訊息編碼,不是傳輸層分塊。
#   v1(func 5)保持不變,RIC 端 xApp 改用 v2 後再移除。
OID_ROOT = "2.25.100789996811842101158541215498991799117"
FULLKPM_V2_RAN_FUNCTION_ID = 7
FULLKPM_V2_OID = f"{OID_ROOT}.1.1"
FULLKPM_V2_FORMAT = "DTFULLKPM-v2"
# OSC e2term SCTP 接收 buffer 8KB:單則壓縮後訊息的上限,留 E2AP 外層與 header 的裕度
_V2_MSG_LIMIT = 6000

_TOP_KEYS = ("timestamp_ms", "scene_sim_ms", "compute_ms", "tick_ms")


# ── v2 事件觸發(func 7 / func 8 共用)────────────────────────
# 自訂 E2SM 應自行定義 EventTriggerDefinition,不應借用 E2SM-KPM 的 ASN.1。v2 定義為 JSON:
#   {"eventTriggerFormat": 1, "reportingPeriodMs": <int>}   Event Trigger Style 1「Periodic」
# 解不出來或超出範圍 → 由呼叫端回 RICsubscriptionFailure。
# 遷移期:RIC 端 xApp 目前送的是 E2SM-KPM Format 1(ASN.1)。E2SM_V2_LEGACY_TRIGGER=on(預設)時
# 仍接受並記警告;RIC 改完後設 off 即只收 JSON。
V2_EVENT_TRIGGER_STYLE = {
    "ricEventTriggerStyleType": 1,
    "ricEventTriggerStyleName": "Periodic",
    "ricEventTriggerFormatType": 1,
    "eventTriggerDefinitionFormat1": {"encoding": "UTF-8 JSON",
                                      "fields": {"eventTriggerFormat": "integer, = 1",
                                                 "reportingPeriodMs": "integer, 100..3600000"}},
}
V2_PERIOD_MIN_MS, V2_PERIOD_MAX_MS = 100, 3_600_000


class EventTriggerError(ValueError):
    """事件觸發不合規;cause = E2AP Cause (group, value)。"""

    def __init__(self, msg: str, cause: tuple[str, str]):
        super().__init__(msg)
        self.cause = cause


def encode_v2_event_trigger(period_ms: int) -> bytes:
    return json.dumps({"eventTriggerFormat": 1, "reportingPeriodMs": int(period_ms)}, separators=(",", ":")).encode("utf-8")


def decode_v2_event_trigger(data: bytes, *, allow_legacy: bool | None = None) -> tuple[int, bool]:
    """→ (reportingPeriodMs, 是否走舊 KPM 格式)。不合規丟 EventTriggerError。"""
    import os
    if allow_legacy is None:
        allow_legacy = (os.environ.get("E2SM_V2_LEGACY_TRIGGER") or "on").strip().lower() in ("on", "1", "true")
    if not data:
        raise EventTriggerError("empty event trigger", ("protocol", "abstract-syntax-error-falsely-constructed-message"))
    try:
        obj = json.loads(bytes(data).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        obj = None
    if isinstance(obj, dict):
        if obj.get("eventTriggerFormat") != 1:
            raise EventTriggerError(f"unsupported eventTriggerFormat {obj.get('eventTriggerFormat')!r}",
                                    ("protocol", "semantic-error"))
        period = obj.get("reportingPeriodMs")
        if not isinstance(period, int) or isinstance(period, bool) or not V2_PERIOD_MIN_MS <= period <= V2_PERIOD_MAX_MS:
            raise EventTriggerError(f"reportingPeriodMs out of range: {period!r}", ("protocol", "semantic-error"))
        return period, False
    if allow_legacy:
        from main.apps.e2_adapter.services.optional.codec.e2_subscription_codec import _load_runtime
        try:
            et = _load_runtime().E2SM_KPM_IEs.E2SM_KPM_EventTriggerDefinition
            et.from_aper(bytes(data))
            fmt, val = et.get_val().get("eventDefinition-formats", (None, {}))
            if fmt == "eventDefinition-Format1":
                period = int(val.get("reportingPeriod", 0))
                if V2_PERIOD_MIN_MS <= period <= V2_PERIOD_MAX_MS:
                    return period, True
                raise EventTriggerError(f"legacy reportingPeriod out of range: {period}", ("protocol", "semantic-error"))
        except EventTriggerError:
            raise
        except Exception:  # noqa: BLE001 — 舊格式也解不出來 → 下面統一回不合規
            pass
    raise EventTriggerError("event trigger is neither v2 JSON nor (allowed) legacy KPM Format 1",
                            ("protocol", "abstract-syntax-error-falsely-constructed-message"))


def encode_fullkpm_v2_ran_function_description() -> bytes:
    rfd = {
        "ranFunctionName": {
            "ranFunctionShortName": "DT-E2SM-FULLKPM",
            "ranFunctionServiceModelOID": FULLKPM_V2_OID,
            "ranFunctionDescription": (
                "DT full-state report, one self-contained report per cell per period "
                "(cell radio meas, served UEs with neighbors, 3GPP TS 28.552 PM counters, BBU status) "
                "plus one node report (unattached UEs, warnings)."
            ),
            "ranFunctionInstance": 0,
        },
        "listOfSupportedEventTriggerStyles": [V2_EVENT_TRIGGER_STYLE],
        "listOfSupportedReportStyles": [
            {
                "ricReportStyleType": FULLKPM_STYLE_TYPE,
                "ricReportStyleName": "Periodic Full-State Report",
                "ricEventTriggerStyleType": 1,
                "indicationHeaderFormat": "JSON {format, timestamp_ms, sn, report, gnb_id, cell_id, report_index, report_count, ue_page, ue_pages}",
                "indicationMessageFormat": "zlib-compressed UTF-8 JSON, one self-contained report",
                "maxIndicationMessageBytes": _V2_MSG_LIMIT,
            },
        ],
    }
    return json.dumps(rfd, separators=(",", ":")).encode("utf-8")


def _split_reports(full_data: dict[str, Any]) -> list[tuple[dict, dict]]:
    """全量 snapshot → [(header 欄位, 報告內容)];每份報告自足(帶時間戳與所屬 gNB / cell)。"""
    top = {k: full_data[k] for k in _TOP_KEYS if k in full_data}
    pm_by_gnb = full_data.get("pm") or {}
    bbu = full_data.get("bbu_status") or {}
    ues = list(full_data.get("ue_status") or [])
    claimed: set[int] = set()
    out: list[tuple[dict, dict]] = []
    for g in full_data.get("e2") or []:
        gnb = g.get("gnb_id")
        # pm / bbu_status 以「gnb-<gnb_id>」為鍵(CU full_kpm_reporter),e2 / ue_status 用 gnb_id 本身
        gkey = f"gnb-{gnb}" if f"gnb-{gnb}" in pm_by_gnb or f"gnb-{gnb}" in bbu else gnb
        for cell in g.get("cells") or []:
            cid = cell.get("cell_id")
            served = [i for i, u in enumerate(ues)
                      if u.get("serving_gnb") == gnb and u.get("serving_pci") == cell.get("pci")]
            claimed.update(served)
            out.append(({"report": "cell", "gnb_id": gnb, "cell_id": cid}, {
                **top, "gnb_id": gnb, "e2_timestamp": g.get("timestamp"),
                "cell": cell,
                "ue_status": [ues[i] for i in served],
                "pm": [r for r in pm_by_gnb.get(gkey, []) if r.get("cell_id") == cid],
                "bbu_status": {**(bbu.get(gkey) or {}), "timestamp": bbu.get("timestamp")} if gkey in bbu else None,
            }))
    out.append(({"report": "node"}, {
        **top,
        "cells": [{"gnb_id": g.get("gnb_id"), "cell_id": c.get("cell_id"), "pci": c.get("pci")}
                  for g in full_data.get("e2") or [] for c in g.get("cells") or []],
        "ue_status": [u for i, u in enumerate(ues) if i not in claimed],
        "warnings": full_data.get("warnings") or [],
    }))
    return out


def _compress(obj: dict) -> bytes:
    import zlib
    return zlib.compress(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), 6)


def _paginate(body: dict, limit: int) -> list[bytes]:
    """一份 cell 報告壓縮後超過上限 → 依 UE 分頁(cell.ues 與 ue_status 同步切)。
    第一頁帶完整 cell 屬性、PM、BBU;後續頁帶識別欄位 + cell 識別 + 該頁 UE。每頁都能單獨解讀。"""
    whole = _compress(body)
    cell = body.get("cell")
    if len(whole) <= limit or cell is None:
        return [whole]
    ids = [u.get("ue_id") for u in cell.get("ues") or []]
    ids += [u.get("ue_id") for u in body.get("ue_status") or [] if u.get("ue_id") not in ids]
    if len(ids) <= 1:
        return [whole]
    ident = {k: body[k] for k in (*_TOP_KEYS, "gnb_id", "e2_timestamp") if k in body}
    cell_id = {k: cell[k] for k in ("cell_id", "ran_name", "pci") if k in cell}

    def page(sel: set, first: bool) -> dict:
        c = {**(cell if first else cell_id), "ues": [u for u in cell.get("ues") or [] if u.get("ue_id") in sel]}
        st = [u for u in body.get("ue_status") or [] if u.get("ue_id") in sel]
        return {**(body if first else ident), "cell": c, "ue_status": st}

    for n in range(2, len(ids) + 1):
        size = -(-len(ids) // n)
        groups = [set(ids[i:i + size]) for i in range(0, len(ids), size)]
        comp = [_compress(page(g, i == 0)) for i, g in enumerate(groups)]
        if all(len(c) <= limit for c in comp):
            return comp
    # 單一 UE 加上 cell 屬性 / PM 仍超過上限:不再切,照送(由 e2term 端回報),不靜默丟資料
    return [_compress(page({i}, k == 0)) for k, i in enumerate(ids)]


def build_indication_payloads_v2(full_data: dict[str, Any], sn: int,
                                 limit: int = _V2_MSG_LIMIT) -> list[tuple[bytes, bytes]]:
    """全量 snapshot → [(header, message)];每則 indication 可單獨解壓、解讀,不需與其他則拼接。"""
    ts = int(full_data.get("timestamp_ms", 0))
    items: list[tuple[dict, bytes, int, int]] = []
    for hdr, body in _split_reports(full_data):
        pages = _paginate(body, limit)
        for p, msg in enumerate(pages):
            items.append((hdr, msg, p, len(pages)))
    total = len(items)
    return [
        (json.dumps({"format": FULLKPM_V2_FORMAT, "timestamp_ms": ts, "sn": int(sn), **hdr,
                     "encoding": "zlib", "report_index": i, "report_count": total,
                     "ue_page": p, "ue_pages": np}, separators=(",", ":")).encode("utf-8"), msg)
        for i, (hdr, msg, p, np) in enumerate(items)
    ]
