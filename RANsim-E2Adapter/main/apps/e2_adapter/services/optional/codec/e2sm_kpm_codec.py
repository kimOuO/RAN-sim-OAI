"""E2SM-KPM codec — KPM Indication Format 3 + RANfunction-Description encoder.

Reference:
  - O-RAN E2SM-KPM v2.0.03 §7.8 (Indication Format 3 — UE-level measurement)
  - Sim CU /E2/Indication/poll payload schema

Format 3 結構：
  E2SM-KPM-IndicationMessage
    .indicationMessage-formats = indicationMessage-Format3
    Format3.ueMeasReportList = [
      UEMeasurementReportItem {
        ueID,
        measReport = E2SM-KPM-IndicationMessage-Format1 {
          measData       = list of MeasurementDataItem (per granul period values)
          measInfoList   = list of MeasurementInfoItem (metric names + labels)
          granulPeriod
        }
      }
    ]
"""
from __future__ import annotations

from typing import Any

from main.apps.e2_adapter.services.optional.codec.e2ap_codec import _load_runtime
from main.utils.logger import get_logger

logger = get_logger(__name__)


def _build_meas_info_list(metric_names: list[str]) -> list[dict[str, Any]]:
    """MeasInfoList — 一筆對應一個 metric name (帶 noLabel=true LabelInfo)."""
    items = []
    for name in metric_names:
        items.append({
            "measType": ("measName", name),
            # LabelInfoList 至少 1 筆（spec 規定，否則 OAI 會 assert crash —
            # 對應 RIC team 講的 P2.5 LabelInfoItem patch 議題）
            "labelInfoList": [
                {"measLabel": {"noLabel": "true"}},
            ],
        })
    return items


def _value_to_kpm_uint(name: str, v: Any) -> Any:
    """3GPP-aligned conversion to non-negative INTEGER for MeasurementRecordItem.

    Per E2SM-KPM: MeasurementRecordItem.integer is uint32 (0..2^32-1).
    Conventions per 3GPP TS 38.133:
      RSRP: -156..-31 dBm → 0..125 (add 156)
      SINR: -23..40 dB → 0..63 (add 23, scale 0.5)
    Other metrics: round to nearest non-negative integer.
    """
    if v is None or isinstance(v, bool):
        return ("noValue", 0)
    name_upper = name.upper()
    if "RSRP" in name_upper:
        # Map -156..-31 → 0..125 per 38.133 §10.1.6.1
        try:
            mapped = int(round(float(v) + 156))
            return ("integer", max(0, min(127, mapped)))
        except (TypeError, ValueError):
            return ("noValue", 0)
    if "SINR" in name_upper:
        # Map -23..40 → 0..127 (scale 1) per 38.133 §10.1.16.1 simplified
        try:
            mapped = int(round(float(v) + 23))
            return ("integer", max(0, min(127, mapped)))
        except (TypeError, ValueError):
            return ("noValue", 0)
    # Everything else: round to non-negative int, OAI default behaviour
    try:
        if isinstance(v, float):
            iv = int(round(v))
        else:
            iv = int(v)
        return ("integer", max(0, min(0xFFFFFFFF, iv)))
    except (TypeError, ValueError):
        return ("noValue", 0)


def _build_meas_data(metric_names: list[str], metric_values: list[Any]) -> list[dict[str, Any]]:
    """MeasData — 對應 measInfoList 順序的 measurement values。

    Format 3 中每個 UE 的 measData 是 list of MeasurementDataItem，
    每個 item 對應一個 granularity period 的 sample。
    """
    items: list[Any] = []
    for name, v in zip(metric_names, metric_values):
        items.append(_value_to_kpm_uint(name, v))
    return [{"measRecord": items}]


def _build_ue_id_choice(ue_id_str: str, amf_ue_ngap_id: int = 0) -> tuple:
    """Build UEID CHOICE — pick gNB CU-CP variant (most common for KPM).

    For our sim, we use ueID as a string converted to integer for amf-UE-NGAP-ID.
    Real OAI uses CHOICE.gNB { amf-UE-NGAP-ID, guami, gNB-CU-UE-F1AP-ID-List }.
    """
    # Extract numeric tail from ue_id (e.g., "ue-001" → 1)
    if amf_ue_ngap_id == 0:
        try:
            tail = "".join(c for c in ue_id_str if c.isdigit())
            amf_ue_ngap_id = int(tail) if tail else 1
        except ValueError:
            amf_ue_ngap_id = 1

    # GUAMI - PLMN/AMF Region/AMF Set/AMF Pointer (use defaults)
    guami = {
        "pLMNIdentity": bytes.fromhex("02f859"),    # 208/095 same as gNB
        "aMFRegionID": (1, 8),       # bit string 8-bit
        "aMFSetID": (1, 10),         # bit string 10-bit
        "aMFPointer": (0, 6),        # bit string 6-bit
    }
    return ("gNB-UEID", {
        "amf-UE-NGAP-ID": amf_ue_ngap_id,
        "guami": guami,
        "gNB-CU-UE-F1AP-ID-List": [{"gNB-CU-UE-F1AP-ID": amf_ue_ngap_id}],
    })


def encode_kpm_indication_message(payload: dict[str, Any]) -> bytes:
    """Encode E2SM-KPM-IndicationMessage Format 3 → APER bytes.

    ``payload`` schema：
      {
        "ue_meas_report_lst": [
          {
            "ue_id": "ue-001",
            "amf_ue_ngap_id": 1,
            "meas_data_lst": [
              {"name": "DRB.UEThpDl", "value": 12345, "unit": "kbps"},
              ...
            ]
          },
          ...
        ]
      }
    """
    rt = _load_runtime()
    msg_cls = rt.E2SM_KPM_IEs.E2SM_KPM_IndicationMessage

    ue_reports = []
    for ue_entry in payload.get("ue_meas_report_lst", []):
        meas_data_list = ue_entry.get("meas_data_lst", [])
        metric_names = [m["name"] for m in meas_data_list]
        metric_values = [m.get("value") for m in meas_data_list]

        # Build per-UE Format1 (containing measInfo+measData+granul)
        format1 = {
            "measData": _build_meas_data(metric_names, metric_values),
            "measInfoList": _build_meas_info_list(metric_names),
            "granulPeriod": 1000,    # ms — 對齊 sim CU 預設 report period
        }

        ue_reports.append({
            "ueID": _build_ue_id_choice(
                ue_entry.get("ue_id", "ue-001"),
                ue_entry.get("amf_ue_ngap_id", 0),
            ),
            "measReport": format1,
        })

    format3 = {"ueMeasReportList": ue_reports}
    msg_value = {"indicationMessage-formats": ("indicationMessage-Format3", format3)}

    msg_cls.set_val(msg_value)
    return msg_cls.to_aper()


def encode_kpm_indication_header(
    collection_start_time_ms: int = 0,
    cell_id: str = "",
) -> bytes:
    """Encode E2SM-KPM-IndicationHeader Format 1 → APER bytes.

    R3 + AI2: senderName 帶 "<cell_name>/<NCI hex>" 兩個 token 給 RIC mobiflow:
      e.g.  "gnb4-c0/0x04dcb91e85"

    Wire format note (RIC parser 對齊):
      - PrintableString X.680 不允許 underscore '_' (只 A-Z a-z 0-9 SPACE '()+,-./:=?)
      - sim 端 cell_id 是 "gnb4_c0", encode 時自動 sanitize '_' → '-'
      - **wire 上實際是 "gnb4-c0/0x04dcb91e85" (連字符不是底線)**
      - RIC parser 建議 regex split: r'[-_/]' 兩邊都接, 之後 normalise 寫 InfluxDB

    Parse 邏輯 (RIC mobiflow 端):
      parts = senderName.split('/', 1)
      cell_name = parts[0].replace('-', '_')   # "gnb4-c0" → "gnb4_c0"
      try: nci_int = int(parts[1], 16) if len(parts) > 1 else None
      except ValueError: nci_int = None        # graceful 退到只 cell_name (RAN-swap-transparent)

    spec: PrintableString SIZE(0..400) OPTIONAL — 不定 sub-format, 我們 inline
    cell+NCI 兩個 token 純 sim convention; 真機 OAI 改送只 NCI 一個 token 時
    parser 上面 split 自然退 graceful.
    """
    rt = _load_runtime()
    hdr_cls = rt.E2SM_KPM_IEs.E2SM_KPM_IndicationHeader

    if collection_start_time_ms == 0:
        import time
        collection_start_time_ms = int(time.time() * 1000)

    ts_bytes = (collection_start_time_ms & 0xFFFFFFFF).to_bytes(4, "big")

    fmt1: dict[str, Any] = {"colletStartTime": ts_bytes}
    if cell_id:
        # PrintableString 規 X.680: A-Z a-z 0-9 SPACE '()+,-./:=?
        # cell_id "gnb4_c0" 含 '_' 不合法, 換成 '-' 給 RIC parser 還原.
        # 截 400 chars (spec ceiling).
        safe = "".join(
            ch if (ch.isalnum() or ch in " '()+,-./:=?") else "-"
            for ch in cell_id
        )
        fmt1["senderName"] = safe[:400]
    hdr_value = {"indicationHeader-formats": ("indicationHeader-Format1", fmt1)}
    hdr_cls.set_val(hdr_value)
    return hdr_cls.to_aper()


def decode_kpm_indication_message(data: bytes) -> dict[str, Any]:
    """Decode KPM Indication Message back to dict (for self-test / debug)."""
    rt = _load_runtime()
    msg_cls = rt.E2SM_KPM_IEs.E2SM_KPM_IndicationMessage
    msg_cls.from_aper(data)
    return msg_cls.get_val()


# ── E2SM-KPM RANfunction-Description encoder ─────────────────
# Sim 廣告給 RIC 的 KPM 能力清單（這個是 RIC team 講的「xApp 必須 strict 解開
# 才會發 SUB_REQ」的 IE）。

# OAI O-RAN compliant 標準 9 個 metric names（對應 sim 端 kpm_indication.py）：
_SIM_SUPPORTED_METRICS = [
    "DRB.UEThpDl",       # bps   (INTEGER)
    "DRB.UEThpUl",       # bps   (INTEGER)
    "DRB.PdcpSduVolumeDL",   # kbit  (INTEGER)
    "DRB.PdcpSduVolumeUL",   # kbit  (INTEGER)
    "DRB.RlcSduDelayDl",     # μs    (INTEGER)
    "RRU.PrbTotDl",          # PPM   (INTEGER)
    "RRU.PrbTotUl",          # PPM   (INTEGER)
    "RSRP",                  # dBm (sim 擴展)
    "SINR",                  # dB  (sim 擴展)
]


def encode_kpm_ran_function_description() -> bytes:
    """Encode E2SM-KPM-RANfunction-Description (v2.0.03) → APER bytes.

    Goes into E2 Setup Request RANfunction-Item.ranFunctionDefinition.
    xApp (mobiflow) decode 這個 IE 拿到 supported event trigger / report styles
    後才會發 RIC_SUB_REQ。

    structure：
      ranFunction-Name        : OID + names
      ric-EventTriggerStyle-List
        Style 1 (Periodic Report) — 對齊 mobiflow 預設
      ric-ReportStyle-List
        Style 1 (E2 Node Measurement) + measInfo list (9 metrics)
    """
    rt = _load_runtime()
    rfd_cls = rt.E2SM_KPM_IEs.E2SM_KPM_RANfunction_Description

    ran_function_name = {
        "ranFunction-ShortName": "ORAN-E2SM-KPM",
        "ranFunction-E2SM-OID": "1.3.6.1.4.1.53148.1.2.2.2",
        "ranFunction-Description": "KPM Monitor for RANsim",
        "ranFunction-Instance": 0,
    }

    # Style 1: Periodic Report — 唯一一個 EventTrigger style
    event_trigger_styles = [
        {
            "ric-EventTriggerStyle-Type": 1,
            "ric-EventTriggerStyle-Name": "Periodic Report",
            "ric-EventTriggerFormat-Type": 1,
        },
    ]

    # 9 個 measurement names → MeasurementInfo-Action-Item list
    meas_action_list = [
        {"measName": name}   # measID 可選，省略
        for name in _SIM_SUPPORTED_METRICS
    ]

    # Style 1: E2 Node Measurement — 對 mobiflow 最常用
    report_styles = [
        {
            "ric-ReportStyle-Type": 1,
            "ric-ReportStyle-Name": "E2 Node Measurement",
            "ric-ActionFormat-Type": 1,
            "measInfo-Action-List": meas_action_list,
            "ric-IndicationHeaderFormat-Type": 1,
            "ric-IndicationMessageFormat-Type": 1,
        },
    ]

    rfd_value = {
        "ranFunction-Name": ran_function_name,
        "ric-EventTriggerStyle-List": event_trigger_styles,
        "ric-ReportStyle-List": report_styles,
    }

    rfd_cls.set_val(rfd_value)
    return rfd_cls.to_aper()


def selftest_kpm_indication_round_trip() -> dict[str, Any]:
    """Encode + decode a sample 2-UE indication, verify structure."""
    sample = {
        "ue_meas_report_lst": [
            {
                "ue_id": "ue-001", "amf_ue_ngap_id": 1,
                "meas_data_lst": [
                    {"name": "DRB.UEThpDl", "value": 12345, "unit": "kbps"},
                    {"name": "RSRP", "value": -85.5, "unit": "dBm"},
                    {"name": "SINR", "value": 12.3, "unit": "dB"},
                ],
            },
            {
                "ue_id": "ue-002", "amf_ue_ngap_id": 2,
                "meas_data_lst": [
                    {"name": "DRB.UEThpDl", "value": 8200, "unit": "kbps"},
                    {"name": "RRU.PrbTotDl", "value": 45.0, "unit": "%"},
                ],
            },
        ],
    }
    encoded = encode_kpm_indication_message(sample)
    header_bytes = encode_kpm_indication_header()
    decoded = decode_kpm_indication_message(encoded)

    # Sanity: extract format selector + UE count
    fmt_choice, fmt_val = decoded["indicationMessage-formats"]
    ue_count = len(fmt_val["ueMeasReportList"])

    return {
        "encoded_message_size": len(encoded),
        "encoded_message_hex_preview": encoded[:32].hex(),
        "encoded_header_size": len(header_bytes),
        "decoded_format": fmt_choice,
        "decoded_ue_count": ue_count,
    }
