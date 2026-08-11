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
