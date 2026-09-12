"""RIC Subscription Request decoder + sim CU REST payload translator.

Reference:
  - O-RAN E2AP §9.2.1 (RIC Subscription Request)
  - O-RAN E2SM-KPM §7.2 (E2SM-KPM-EventTriggerDefinition Format 1)
  - O-RAN E2SM-KPM §7.6 (E2SM-KPM-ActionDefinition Format 1..5)

xApp-side:                          adapter:
  RIC_SUBSCRIPTION_REQ APER bytes ─► decode_ric_subscription_request() ─►
                                    ─► sim CU /E2/Subscription/create JSON

ProtocolIE IDs:
  29  RICrequestID
  5   RANfunctionID
  30  RICsubscriptionDetails
"""
from __future__ import annotations

from typing import Any

from main.apps.e2_adapter.services.optional.codec.e2ap_codec import _load_runtime
from main.utils.logger import get_logger

logger = get_logger(__name__)

_IE_ID_RICrequestID = 29
_IE_ID_RANfunctionID = 5
_IE_ID_RICsubscriptionDetails = 30
_IE_ID_RICactionsAdmittedList = 17
_IE_ID_RICactionAdmittedItem = 14
# RICindication IEs
_IE_ID_RICactionID = 15
_IE_ID_RICindicationSN = 27
_IE_ID_RICindicationType = 28
_IE_ID_RICindicationHeader = 25
_IE_ID_RICindicationMessage = 26
# Procedure codes
_PROC_CODE_RICsubscription = 8
_PROC_CODE_RICindication = 5


def decode_ric_subscription_request(data: bytes) -> dict[str, Any]:
    """Decode E2AP-PDU APER bytes containing RICsubscriptionRequest.

    Returns sim CU /E2/Subscription/create JSON payload structure.
    """
    rt = _load_runtime()
    pdu_cls = rt.E2AP_PDU_Descriptions.E2AP_PDU
    pdu_cls.from_aper(data)
    decoded = pdu_cls.get_val()

    outcome_choice, outcome_val = decoded
    if outcome_choice != "initiatingMessage":
        raise ValueError(f"expected initiatingMessage, got {outcome_choice}")

    inner = outcome_val["value"]
    if inner[0] != "RICsubscriptionRequest":
        raise ValueError(f"expected RICsubscriptionRequest, got {inner[0]}")

    sub_req = inner[1]

    ric_req_id: dict[str, int] = {}
    ran_func_id: int = 0
    sub_details: dict[str, Any] = {}

    for ie in sub_req.get("protocolIEs", []):
        ie_id = ie.get("id")
        ie_value = ie.get("value")
        if not isinstance(ie_value, tuple):
            continue
        _, val = ie_value

        if ie_id == _IE_ID_RICrequestID:
            ric_req_id = {
                "requestor_id": val.get("ricRequestorID", 0),
                "instance_id": val.get("ricInstanceID", 0),
            }
        elif ie_id == _IE_ID_RANfunctionID:
            ran_func_id = int(val)
        elif ie_id == _IE_ID_RICsubscriptionDetails:
            sub_details = val

    # ricEventTriggerDefinition is OCTET STRING containing E2SM-KPM-EventTriggerDef
    event_trig_bytes: bytes = sub_details.get("ricEventTriggerDefinition", b"")
    actions = sub_details.get("ricAction-ToBeSetup-List", [])

    # Decode E2SM-KPM event trigger inside the OCTET STRING
    report_period_ms = _decode_event_trigger_period(event_trig_bytes)

    # Decode each action
    action_list_translated: list[dict[str, Any]] = []
    for act_ie in actions:
        act_val = act_ie.get("value")
        if not isinstance(act_val, tuple):
            continue
        _, act = act_val
        action_def_bytes: bytes = act.get("ricActionDefinition", b"")
        metrics = _decode_action_metrics(action_def_bytes)
        action_list_translated.append({
            "ric_action_id": act.get("ricActionID"),
            "ric_action_type": act.get("ricActionType"),  # 'report' / 'insert' / 'policy'
            "metrics": metrics,
        })

    # Translate to sim CU /E2/Subscription/create payload
    sim_payload = {
        "service_model": _service_model_from_ran_func_id(ran_func_id),
        "ran_function_id": ran_func_id,
        "ric_req_id": ric_req_id,
        "event_trigger": {
            "format": 1,
            "report_period_ms": report_period_ms,
        },
        # Actions[0] decides what's reported (typical: only 1 action per sub)
        "action_definition": {
            "metrics": action_list_translated[0]["metrics"] if action_list_translated else [],
            "report_period_ms": report_period_ms,
            "ue_filter": {},
        },
    }
    return sim_payload


def _service_model_from_ran_func_id(rf_id: int) -> str:
    """Per RIC team convention: 2=KPM, 3=RC."""
    return {2: "KPM", 3: "RC"}.get(rf_id, "UNKNOWN")


def _decode_event_trigger_period(data: bytes) -> int:
    """Decode E2SM-KPM-EventTriggerDefinition Format 1 → report_period_ms.

    Schema:
      E2SM-KPM-EventTriggerDefinition-Format1 ::= SEQUENCE {
        reportingPeriod  INTEGER (1..4294967295)   -- in ms
      }
    """
    if not data:
        return 1000  # default
    try:
        rt = _load_runtime()
        et_cls = rt.E2SM_KPM_IEs.E2SM_KPM_EventTriggerDefinition
        et_cls.from_aper(data)
        val = et_cls.get_val()
        # CHOICE wrapper: (format-name, format-value)
        fmt_choice, fmt_val = val.get("eventDefinition-formats", (None, {}))
        if fmt_choice == "eventDefinition-Format1":
            return int(fmt_val.get("reportingPeriod", 1000))
    except Exception as exc:
        logger.warning("failed to decode event trigger: %s — using default 1000ms", exc)
    return 1000


def _decode_action_metrics(data: bytes) -> list[str]:
    """Decode E2SM-KPM-ActionDefinition (any Format) → list of metric names.

    For Format 1: ric-Style-Type=1 + measInfoList[].measType.measName
    For Format 5: ric-Style-Type=5 + matchingUEidList per UE granularity
    """
    if not data:
        return []
    try:
        rt = _load_runtime()
        ad_cls = rt.E2SM_KPM_IEs.E2SM_KPM_ActionDefinition
        ad_cls.from_aper(data)
        val = ad_cls.get_val()
        # Format selector + per-format value
        fmt_choice, fmt_val = val.get("actionDefinition-formats", (None, {}))
        meas_info_list = []
        if fmt_choice in ("actionDefinition-Format1", "actionDefinition-Format2"):
            meas_info_list = fmt_val.get("measInfoList", [])
        elif fmt_choice == "actionDefinition-Format3":
            meas_info_list = fmt_val.get("measCondList", [])
        # 從 measType CHOICE 抽 measName string
        names: list[str] = []
        for item in meas_info_list:
            mt = item.get("measType")
            if isinstance(mt, tuple) and mt[0] == "measName":
                names.append(str(mt[1]))
        return names
    except Exception as exc:
        logger.warning("failed to decode action definition: %s", exc)
        return []


def encode_ric_subscription_response(
    ric_req_id: dict[str, int],
    ran_function_id: int,
    admitted_action_ids: list[int],
) -> bytes:
    """Encode RIC Subscription Response (successful) → APER E2AP-PDU bytes.

    Per E2AP §9.2.2:
      protocolIEs:
        id=29 RICrequestID         (echo)
        id=5  RANfunctionID        (echo)
        id=17 RICactions-Admitted-List  (list of admitted action IDs)
    """
    rt = _load_runtime()
    pdu_cls = rt.E2AP_PDU_Descriptions.E2AP_PDU

    admitted_list = []
    for aid in admitted_action_ids:
        admitted_list.append({
            "id": _IE_ID_RICactionAdmittedItem,
            "criticality": "ignore",
            "value": ("RICaction-Admitted-Item", {"ricActionID": aid}),
        })

    sub_resp = {
        "protocolIEs": [
            {"id": _IE_ID_RICrequestID, "criticality": "reject",
             "value": ("RICrequestID", {
                 "ricRequestorID": ric_req_id.get("requestor_id", 0),
                 "ricInstanceID": ric_req_id.get("instance_id", 0),
             })},
            {"id": _IE_ID_RANfunctionID, "criticality": "reject",
             "value": ("RANfunctionID", ran_function_id)},
            {"id": _IE_ID_RICactionsAdmittedList, "criticality": "reject",
             "value": ("RICaction-Admitted-List", admitted_list)},
        ],
    }

    pdu_cls.set_val(("successfulOutcome", {
        "procedureCode": _PROC_CODE_RICsubscription,
        "criticality": "reject",
        "value": ("RICsubscriptionResponse", sub_resp),
    }))
    return pdu_cls.to_aper()


def encode_ric_indication(
    ric_req_id: dict[str, int],
    ran_function_id: int,
    action_id: int,
    indication_sn: int,
    indication_header: bytes,
    indication_message: bytes,
    indication_type: str = "report",
) -> bytes:
    """Encode RIC Indication → APER E2AP-PDU bytes.

    Per E2AP §9.2.3:
      protocolIEs:
        id=29 RICrequestID
        id=5  RANfunctionID
        id=15 RICactionID
        id=27 RICindicationSN
        id=28 RICindicationType (report/insert)
        id=25 RICindicationHeader   ← E2SM-KPM-IndicationHeader APER bytes
        id=26 RICindicationMessage  ← E2SM-KPM-IndicationMessage APER bytes
    """
    rt = _load_runtime()
    pdu_cls = rt.E2AP_PDU_Descriptions.E2AP_PDU

    ind_value = {
        "protocolIEs": [
            {"id": _IE_ID_RICrequestID, "criticality": "reject",
             "value": ("RICrequestID", {
                 "ricRequestorID": ric_req_id.get("requestor_id", 0),
                 "ricInstanceID": ric_req_id.get("instance_id", 0),
             })},
            {"id": _IE_ID_RANfunctionID, "criticality": "reject",
             "value": ("RANfunctionID", ran_function_id)},
            {"id": _IE_ID_RICactionID, "criticality": "reject",
             "value": ("RICactionID", action_id)},
            {"id": _IE_ID_RICindicationSN, "criticality": "reject",
             "value": ("RICindicationSN", indication_sn)},
            {"id": _IE_ID_RICindicationType, "criticality": "reject",
             "value": ("RICindicationType", indication_type)},
            {"id": _IE_ID_RICindicationHeader, "criticality": "reject",
             "value": ("RICindicationHeader", indication_header)},
            {"id": _IE_ID_RICindicationMessage, "criticality": "reject",
             "value": ("RICindicationMessage", indication_message)},
        ],
    }

    pdu_cls.set_val(("initiatingMessage", {
        "procedureCode": _PROC_CODE_RICindication,
        "criticality": "ignore",
        "value": ("RICindication", ind_value),
    }))
    return pdu_cls.to_aper()


def selftest_subscription_decode_round_trip() -> dict[str, Any]:
    """Self-test: build a fake RIC_SUB_REQ + decode → translate to sim payload."""
    # We don't have an "encoder" for SUB_REQ (xApp side does that), but pycrate
    # 設計上同時可 encode/decode。寫個假 SUB_REQ 編出來，再 decode 驗證。
    rt = _load_runtime()
    pdu_cls = rt.E2AP_PDU_Descriptions.E2AP_PDU
    et_cls = rt.E2SM_KPM_IEs.E2SM_KPM_EventTriggerDefinition
    ad_cls = rt.E2SM_KPM_IEs.E2SM_KPM_ActionDefinition

    # Build event trigger Format 1 — period 1000ms
    et_cls.set_val({"eventDefinition-formats": ("eventDefinition-Format1",
                                                  {"reportingPeriod": 1000})})
    event_trig_bytes = et_cls.to_aper()

    # Build action def Format 1 — measure DRB.UEThpDl + RSRP
    ad_cls.set_val({
        "ric-Style-Type": 1,
        "actionDefinition-formats": ("actionDefinition-Format1", {
            "measInfoList": [
                {
                    "measType": ("measName", "DRB.UEThpDl"),
                    "labelInfoList": [{"measLabel": {"noLabel": "true"}}],
                },
                {
                    "measType": ("measName", "RSRP"),
                    "labelInfoList": [{"measLabel": {"noLabel": "true"}}],
                },
            ],
            "granulPeriod": 1000,
        }),
    })
    action_def_bytes = ad_cls.to_aper()

    # Build RIC SUB REQ
    sub_req_value = {
        "protocolIEs": [
            {"id": 29, "criticality": "reject",
             "value": ("RICrequestID", {"ricRequestorID": 1234, "ricInstanceID": 5})},
            {"id": 5, "criticality": "reject",
             "value": ("RANfunctionID", 2)},
            {"id": 30, "criticality": "reject",
             "value": ("RICsubscriptionDetails", {
                 "ricEventTriggerDefinition": event_trig_bytes,
                 "ricAction-ToBeSetup-List": [
                     {"id": 19, "criticality": "reject",
                      "value": ("RICaction-ToBeSetup-Item", {
                          "ricActionID": 0,
                          "ricActionType": "report",
                          "ricActionDefinition": action_def_bytes,
                      })},
                 ],
             })},
        ],
    }
    pdu_cls.set_val(("initiatingMessage", {
        "procedureCode": 8,    # ricSubscription
        "criticality": "reject",
        "value": ("RICsubscriptionRequest", sub_req_value),
    }))
    raw = pdu_cls.to_aper()

    # Now decode + translate
    sim_payload = decode_ric_subscription_request(raw)
    return {
        "encoded_size": len(raw),
        "decoded_sim_payload": sim_payload,
    }
