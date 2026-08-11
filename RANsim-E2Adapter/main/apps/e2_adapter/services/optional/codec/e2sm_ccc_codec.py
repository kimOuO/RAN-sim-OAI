"""E2SM-CCC codec — Cell Configuration and Control(cell 開關 / 節能)。

參考:
  - O-RAN.WG3.E2SM-CCC(R003 v04+),OID 1.3.6.1.4.1.53148.1.1.2.4,RAN function ID 預設 4
  - 封裝已對 srsRAN oran-sc-ric CCC 實作逐字驗證(見 docs/api/e2sm_ccc_cell_control.md)
  - 對接格式文件:docs/api/e2sm_ccc_cell_control.md

★ 與 E2SM-RC 最大差異:CCC 的 RIC Control Header / Message 是 **JSON**(不是 ASN.1)。
  E2AP 外層(取 ran_function_id + header/message OCTET STRING)照 RC 解;內層直接 json.loads。

Control Header (JSON): { "controlHeaderFormat": { "ricStyleType": 2 } }
Control Message (JSON):
  { "controlMessageFormat": { "listOfCellsControlled": [
      { "cellGlobalId": {"plmnIdentity":{"mcc","mnc"}, "nRCellIdentity": "..."},
        "listOfConfigurationStructures": [
          { "ranConfigurationStructureName": "NRCellDU" | "O-CESManagementFunction",
            "oldValuesOfAttributes": {...}, "newValuesOfAttributes": {...} } ] } ] } }
"""
from __future__ import annotations

import json
from typing import Any

from main.apps.e2_adapter.services.optional.codec.e2ap_codec import _load_runtime
from main.utils.logger import get_logger

logger = get_logger(__name__)

CCC_RAN_FUNCTION_ID = 4
CCC_OID = "1.3.6.1.4.1.53148.1.1.2.4"
CCC_RIC_STYLE_TYPE = 2  # Cell Configuration and Control


# ── cell 開關語意:從 newValuesOfAttributes 判斷 on/off ─────────────
def _action_from_attrs(struct_name: str, new_vals: dict[str, Any]) -> tuple[str | None, bool]:
    """回傳 (action, staged)。action='off'/'on'/None;staged=True 代表走節能兩階段
       (toBeEnergySaving→趕人→isEnergySaving),False 代表硬開關(即時)。
       - O-CESManagementFunction.energySavingControl:toBeEnergySaving=off / toBeNotEnergySaving=on → staged
       - energySavingState:isEnergySaving=off / isNotEnergySaving=on → staged
       - NRCellDU.administrativeState:LOCKED=off / UNLOCKED=on → hard(3GPP,直接開關)
       - NRCellDU.cellState:INACTIVE=off / ACTIVE=on → hard
    """
    def norm(v: Any) -> str:
        return str(v).strip().lower()

    esc = new_vals.get("energySavingControl")
    if esc is not None:
        n = norm(esc)
        if n == "tobeenergysaving":
            return "off", True
        if n == "tobenotenergysaving":
            return "on", True

    ess = new_vals.get("energySavingState")
    if ess is not None:
        n = norm(ess)
        if n == "isenergysaving":
            return "off", True
        if n == "isnotenergysaving":
            return "on", True

    admin = new_vals.get("administrativeState")
    if admin is not None:
        n = norm(admin)
        if n == "locked":
            return "off", False
        if n == "unlocked":
            return "on", False

    cstate = new_vals.get("cellState")
    if cstate is not None:
        n = norm(cstate)
        if n == "inactive":
            return "off", False
        if n == "active":
            return "on", False
    return None, False


def _cell_id_from_global(cgi: dict[str, Any]) -> str:
    """cellGlobalId → 字串 cell 識別(交給 sim CU 解析成內部 cell_id)。
    優先 nRCellIdentity;沒有就用 plmn+identity 組。"""
    nrci = cgi.get("nRCellIdentity") or cgi.get("nrCellIdentity")
    if nrci is not None:
        return str(nrci)
    plmn = cgi.get("plmnIdentity") or {}
    return f"{plmn.get('mcc','')}{plmn.get('mnc','')}"


# ── E2AP 外層解碼(與 RC 相同:取 ran_function_id + header/message)──
def decode_ric_control_request(data: bytes) -> dict[str, Any]:
    """Decode RIC Control Request(CCC）→ dict。
    Returns:
      { ric_req_id, ran_function_id, ric_style_type,
        cells: [{cell_id, action:'on'|'off', struct, new_vals}],
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

    # 內層 CCC 是 JSON
    ric_style_type = 0
    try:
        hdr = json.loads(header_bytes.decode("utf-8")) if header_bytes else {}
        ric_style_type = int(hdr.get("controlHeaderFormat", {}).get("ricStyleType", 0))
    except Exception as exc:  # noqa: BLE001
        logger.warning("CCC control header JSON decode failed: %s", exc)

    cells: list[dict[str, Any]] = []
    try:
        msg = json.loads(message_bytes.decode("utf-8")) if message_bytes else {}
        cmf = msg.get("controlMessageFormat", {})
        for cell in cmf.get("listOfCellsControlled", []) or []:
            cid = _cell_id_from_global(cell.get("cellGlobalId", {}))
            for cs in cell.get("listOfConfigurationStructures", []) or []:
                sname = cs.get("ranConfigurationStructureName", "")
                new_vals = cs.get("newValuesOfAttributes", {}) or {}
                action, staged = _action_from_attrs(sname, new_vals)
                cells.append({
                    "cell_id": cid, "action": action, "staged": staged,
                    "struct": sname, "new_vals": new_vals,
                })
    except Exception as exc:  # noqa: BLE001
        logger.warning("CCC control message JSON decode failed: %s", exc)

    return {
        "ric_req_id": ric_req_id,
        "ran_function_id": ran_function_id,
        "ric_style_type": ric_style_type,
        "cells": cells,
        "raw_header_bytes": len(header_bytes),
        "raw_message_bytes": len(message_bytes),
    }


def to_sim_control_payload(ccc_decoded: dict[str, Any]) -> dict[str, Any] | None:
    """CCC decoded → sim CU /CU/E2/Control/request payload(cell 開關）。
      { ric_req_id, ran_function_id, sim_action:'control_cell_onoff',
        cells: [{cell_id, action:'enable'|'disable'}] }
    """
    cells = []
    for c in ccc_decoded.get("cells", []):
        act = c.get("action")
        if act not in ("on", "off"):
            continue
        cells.append({
            "cell_id": c["cell_id"],
            "action": "enable" if act == "on" else "disable",
            "staged": bool(c.get("staged", False)),  # True=節能兩階段;False=硬開關
        })
    if not cells:
        return None
    return {
        "ric_req_id": ccc_decoded.get("ric_req_id", {}),
        "ran_function_id": ccc_decoded.get("ran_function_id", CCC_RAN_FUNCTION_ID),
        "sim_action": "control_cell_onoff",
        "cells": cells,
    }


def encode_ccc_ran_function_description() -> bytes:
    """CCC RAN Function Definition — E2SM-CCC 用 JSON。E2 Setup 廣播用。
    宣告我方支援的 cell-level 設定結構 + 讀寫能力。
    (schema 標 [M],確切欄位待 O-RAN spec PDF 定版;見 docs/api/e2sm_ccc_cell_control.md)
    """
    rfd = {
        "ranFunctionName": {
            "ranFunctionShortName": "ORAN-E2SM-CCC",
            "ranFunctionServiceModelOID": CCC_OID,
            "ranFunctionDescription": "Cell Configuration and Control (cell on/off / energy saving)",
        },
        "listOfSupportedCellLevelRICControlStyles": [
            {"ricStyleType": CCC_RIC_STYLE_TYPE, "ricStyleName": "Cell Configuration and Control"},
        ],
        "listOfCellLevelRANConfigurationStructures": [
            {"ranConfigurationStructureName": "NRCellDU",
             "attributes": [
                 {"name": "administrativeState", "access": "READ_WRITE"},
                 {"name": "cellState", "access": "READ_WRITE"},
                 {"name": "operationalState", "access": "READ_ONLY"},
             ]},
            {"ranConfigurationStructureName": "O-CESManagementFunction",
             "attributes": [
                 {"name": "energySavingControl", "access": "READ_WRITE"},
                 {"name": "energySavingState", "access": "READ_ONLY"},
                 {"name": "cesSwitch", "access": "READ_WRITE"},
             ]},
        ],
    }
    return json.dumps(rfd, separators=(",", ":")).encode("utf-8")


# ── CCC RIC Indication(回報 cell 狀態變化給 xApp;E2AP 外層複用 encode_ric_indication)──
def encode_ccc_indication_header() -> bytes:
    return json.dumps(
        {"indicationHeaderFormat": {"ricStyleType": CCC_RIC_STYLE_TYPE}},
        separators=(",", ":"),
    ).encode("utf-8")


def encode_ccc_indication_message(cell_id: str, energy_saving_state: str,
                                  plmn: dict | None = None) -> bytes:
    """回報某 cell 的 energySavingState(isNotEnergySaving/toBeEnergySaving/isEnergySaving)。"""
    cgi: dict[str, Any] = {"nRCellIdentity": cell_id}
    if plmn:
        cgi["plmnIdentity"] = plmn
    msg = {
        "indicationMessageFormat": {
            "listOfCellsReported": [
                {
                    "cellGlobalId": cgi,
                    "listOfConfigurationStructuresReported": [
                        {
                            "ranConfigurationStructureName": "O-CESManagementFunction",
                            "valuesOfAttributes": {"energySavingState": energy_saving_state},
                        }
                    ],
                }
            ]
        }
    }
    return json.dumps(msg, separators=(",", ":")).encode("utf-8")


# ── self-test:驗證 JSON 內層 decode 邏輯(不含 E2AP 外層 ASN.1)──
def selftest_ccc_decode() -> dict[str, Any]:
    """建一組 CCC header/message JSON,直接測 on/off 判定邏輯。"""
    hdr = {"controlHeaderFormat": {"ricStyleType": CCC_RIC_STYLE_TYPE}}
    msg = {"controlMessageFormat": {"listOfCellsControlled": [
        {"cellGlobalId": {"plmnIdentity": {"mcc": "001", "mnc": "01"},
                          "nRCellIdentity": "gnbDT_c0"},
         "listOfConfigurationStructures": [
             {"ranConfigurationStructureName": "NRCellDU",
              "oldValuesOfAttributes": {"administrativeState": "UNLOCKED"},
              "newValuesOfAttributes": {"administrativeState": "LOCKED"}}]},
    ]}}
    # 模擬內層 decode(略過 E2AP 外層)
    style = int(hdr["controlHeaderFormat"]["ricStyleType"])
    cells = []
    for cell in msg["controlMessageFormat"]["listOfCellsControlled"]:
        cid = _cell_id_from_global(cell["cellGlobalId"])
        for cs in cell["listOfConfigurationStructures"]:
            act, staged = _action_from_attrs(cs["ranConfigurationStructureName"],
                                             cs["newValuesOfAttributes"])
            cells.append({"cell_id": cid, "action": act, "staged": staged})
    payload = to_sim_control_payload({"ric_req_id": {}, "ran_function_id": CCC_RAN_FUNCTION_ID,
                                      "cells": cells})
    rfd_ok = len(encode_ccc_ran_function_description()) > 0
    return {"style": style, "cells": cells, "sim_payload": payload, "rfd_encoded": rfd_ok}
