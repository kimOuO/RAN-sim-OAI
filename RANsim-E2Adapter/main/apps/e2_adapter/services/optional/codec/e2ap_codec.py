"""E2AP PDU encoder/decoder — APER over SCTP.

Uses pycrate-generated runtime module at ``_generated/pycrate_e2.py``.

Reference:
  - O-RAN E2AP v2.0.3 §9.1.1.1 (E2 Setup Request)
  - O-RAN E2AP v2.0.3 §9.2.4 (ASN.1 PDU definitions)
  - O-RAN E2AP v2.0.3 §9.1.1.5 (GlobalE2node-ID)

ProtocolIE IDs used in E2 Setup Request:
  3   GlobalE2node-ID                    (mandatory)
  10  RANfunctionsAdded                  (mandatory, list)
  50  E2nodeComponentConfigAddition      (mandatory in v2.0.3, list)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from main.utils.logger import get_logger

logger = get_logger(__name__)

# ProtocolIE IDs (E2AP-Constants §9.x)
_IE_ID_TransactionID = 49
_IE_ID_GlobalE2NodeID = 3
_IE_ID_RANfunctionsAdded = 10
_IE_ID_E2nodeComponentConfigAddition = 50
_IE_ID_Cause = 1

# RANfunction IE IDs (sub-IE of RANfunction-Item)
_IE_ID_RANfunctionItem = 8

# E2 Setup procedureCode
_PROC_CODE_E2_SETUP = 1
# E2 Reset procedureCode (E2AP §9.3.7 / id-Reset)
_PROC_CODE_E2_RESET = 3


# Process-local TransactionID counter (1..255 wrap)
_tid_counter = 0


def _next_transaction_id() -> int:
    global _tid_counter
    _tid_counter = (_tid_counter % 255) + 1
    return _tid_counter


# Lazy-loaded pycrate runtime module
_runtime = None


def _runtime_path() -> Path:
    return Path(__file__).parent / "_generated" / "pycrate_e2.py"


def _load_runtime():
    """Import the generated pycrate runtime module (one-time, cached)."""
    global _runtime
    if _runtime is not None:
        return _runtime
    gen_dir = str(_runtime_path().parent)
    if gen_dir not in sys.path:
        sys.path.insert(0, gen_dir)
    if not _runtime_path().exists():
        raise RuntimeError(
            f"pycrate runtime not generated yet: {_runtime_path()}. "
            f"Run shell/generate_pycrate_runtime.py during build."
        )
    import pycrate_e2  # type: ignore
    _runtime = pycrate_e2
    return _runtime


def is_runtime_ready() -> bool:
    """For /Status/read — does the encoder have its compiled module?"""
    try:
        _load_runtime()
        return True
    except Exception:
        return False


# ── PLMN encoding helper ─────────────────────────────────────────
def _encode_plmn_id(mcc: str, mnc: str, mnc_digit_count: int = 0) -> bytes:
    """Encode PLMN-Identity (3 bytes BCD) per 3GPP TS 24.008 §10.5.1.3.

    For MCC=208, MNC=95 (2-digit):
      byte 1 = MCC2|MCC1 = 0|2  → 0x02
      byte 2 = MNC3|MCC3 = F|8  → 0xF8   (F = filler for 2-digit MNC)
      byte 3 = MNC2|MNC1 = 5|9  → 0x59

    ``mnc_digit_count`` 0=auto-detect by len(mnc).  Sim CU 把原始 digit count 帶在
    payload 裡，adapter 直接拿，避免 zfill 後判斷錯。
    """
    if not (mcc.isdigit() and len(mcc) == 3):
        raise ValueError(f"MCC must be 3 digits: {mcc!r}")

    if mnc_digit_count == 0:
        mnc_digit_count = len(mnc)
    mnc_padded = mnc.zfill(3) if len(mnc) < 3 else mnc
    if not mnc_padded.isdigit() or len(mnc_padded) != 3:
        raise ValueError(f"MNC must be 1-3 digits: {mnc!r}")

    is_2digit_mnc = (mnc_digit_count == 2)

    # MCC1=hundreds, MCC2=tens, MCC3=units
    m1, m2, m3 = int(mcc[0]), int(mcc[1]), int(mcc[2])

    if is_2digit_mnc:
        # 2-digit MNC: real digits are last 2 of padded ("095" → tens=9, units=5)
        # n1=tens, n2=units
        n1, n2 = int(mnc_padded[1]), int(mnc_padded[2])
        # Octet1: MCC2|MCC1 ; Octet2: 0xF|MCC3 (filler) ; Octet3: MNC2|MNC1
        b1 = (m2 << 4) | m1
        b2 = (0xF << 4) | m3
        b3 = (n2 << 4) | n1
    else:
        # 3-digit MNC: all 3 digits real
        n1, n2, n3 = int(mnc_padded[0]), int(mnc_padded[1]), int(mnc_padded[2])
        # Octet1: MCC2|MCC1 ; Octet2: MNC3|MCC3 ; Octet3: MNC2|MNC1
        b1 = (m2 << 4) | m1
        b2 = (n3 << 4) | m3
        b3 = (n2 << 4) | n1
    return bytes([b1, b2, b3])


# ── E2 Setup Request encoder ─────────────────────────────────────
def encode_e2_setup_request(node_id_payload: dict[str, Any]) -> bytes:
    """Encode E2 Setup Request → APER bytes.

    ``node_id_payload`` is the dict returned by sim CU /CU/E2/E2NodeId/read:
      {
        "global_e2_node_id": {
          "plmn_id": {"mcc": "208", "mnc": "095"},
          "gnb_id": {"value_int": 56, "bit_length": 22},
        },
        "ran_functions": [
          {"ran_function_id": 2, "ran_function_oid": "1.3...", ...},
          ...
        ],
      }
    """
    rt = _load_runtime()
    pdu_cls = rt.E2AP_PDU_Descriptions.E2AP_PDU

    gid = node_id_payload["global_e2_node_id"]
    plmn_bytes = _encode_plmn_id(
        gid["plmn_id"]["mcc"],
        gid["plmn_id"]["mnc"],
        gid["plmn_id"].get("mnc_digit_count", 0),
    )

    # GNB-ID-Choice: gnb-ID is BIT STRING. pycrate accepts (int_value, bit_count) tuple.
    gnb_id_int = gid["gnb_id"]["value_int"]
    gnb_id_bits = gid["gnb_id"]["bit_length"]
    gnb_id_bitstr = (gnb_id_int, gnb_id_bits)

    # GlobalgNB-ID
    global_gnb_id_value = {
        "plmn-id": plmn_bytes,
        "gnb-id": ("gnb-ID", gnb_id_bitstr),
    }

    # GlobalE2node-gNB-ID
    global_e2node_gnb_id_value = {
        "global-gNB-ID": global_gnb_id_value,
    }

    # GlobalE2node-ID (CHOICE, pick gNB)
    global_e2_node_id_value = ("gNB", global_e2node_gnb_id_value)

    # ── TransactionID（mandatory，per E2AP v2.0.3 §9.1.1.1）─────
    ie_transaction = {
        "id": _IE_ID_TransactionID,
        "criticality": "reject",
        "value": ("TransactionID", _next_transaction_id()),
    }

    # ── ProtocolIE container for GlobalE2node-ID ─────────────
    ie_globalid = {
        "id": _IE_ID_GlobalE2NodeID,
        "criticality": "reject",
        "value": ("GlobalE2node-ID", global_e2_node_id_value),
    }

    # ── RANfunctionsAdded (list) ─────────────────────────────
    # Each item: RANfunction_ItemIEs containing { id=8, criticality, value=RANfunction-Item }
    # xApp 對 RANfunctionDefinition 多採 strict decode；stub 0x00000000 會 fail。
    # 對 KPM (id=2) / RC (id=3) 都編真實 RANfunction-Description.
    from main.apps.e2_adapter.services.optional.codec import e2sm_kpm_codec, e2sm_rc_codec

    ran_func_items = []
    for rf in node_id_payload["ran_functions"]:
        sm = rf.get("service_model", "").upper()
        if sm == "KPM":
            try:
                rfd_bytes = e2sm_kpm_codec.encode_kpm_ran_function_description()
            except Exception:
                logger.exception("KPM RANfunction-Description encode failed; using empty stub")
                rfd_bytes = b""
        elif sm == "RC":
            try:
                rfd_bytes = e2sm_rc_codec.encode_rc_ran_function_description()
            except Exception:
                logger.exception("RC RANfunction-Description encode failed; using empty stub")
                rfd_bytes = b""
        else:
            logger.warning("Unknown service_model %r for ranFunction id=%s",
                           sm, rf.get("ran_function_id"))
            rfd_bytes = b""

        rf_item = {
            "ranFunctionID": rf["ran_function_id"],
            "ranFunctionDefinition": rfd_bytes,
            "ranFunctionRevision": rf["ran_function_revision"],
            "ranFunctionOID": rf["ran_function_oid"],
        }
        ran_func_items.append({
            "id": _IE_ID_RANfunctionItem,
            "criticality": "reject",
            "value": ("RANfunction-Item", rf_item),
        })

    ie_ran_funcs = {
        "id": _IE_ID_RANfunctionsAdded,
        "criticality": "reject",
        "value": ("RANfunctions-List", ran_func_items),
    }

    # ── E2nodeComponentConfigAddition (mandatory list) ──────────
    # Minimal: 1 item describing our gNB component. Use NG interface as default.
    component_item = {
        "e2nodeComponentInterfaceType": "ng",
        "e2nodeComponentID": ("e2nodeComponentInterfaceTypeNG",
                              {"amf-name": "AMF-Mock"}),
        "e2nodeComponentConfiguration": {
            "e2nodeComponentRequestPart": b"",
            "e2nodeComponentResponsePart": b"",
        },
    }
    ie_components = {
        "id": _IE_ID_E2nodeComponentConfigAddition,
        "criticality": "reject",
        "value": ("E2nodeComponentConfigAddition-List", [
            {
                "id": 51,    # ProtocolIE-ID for E2nodeComponentConfigAddition-Item
                "criticality": "reject",
                "value": ("E2nodeComponentConfigAddition-Item", component_item),
            },
        ]),
    }

    # ── Build E2setupRequest SEQ ────────────────────────────
    # 順序：TransactionID → GlobalE2node-ID → RANfunctionsAdded → E2nodeComponentConfigAddition
    e2setup_request_value = {
        "protocolIEs": [ie_transaction, ie_globalid, ie_ran_funcs, ie_components],
    }

    # ── InitiatingMessage SEQ ────────────────────────────────
    initiating_msg_value = {
        "procedureCode": _PROC_CODE_E2_SETUP,
        "criticality": "reject",
        "value": ("E2setupRequest", e2setup_request_value),
    }

    # ── E2AP-PDU CHOICE ──────────────────────────────────────
    pdu_value = ("initiatingMessage", initiating_msg_value)

    pdu_cls.set_val(pdu_value)
    return pdu_cls.to_aper()


# ── E2 Reset Request encoder ─────────────────────────────────────
def encode_e2_reset_request(cause_misc: str = "om-intervention") -> bytes:
    """Encode E2 Reset Request → APER bytes (E2AP §9.1.1.3).

    Mandatory IEs:
      id=49  TransactionID    criticality=reject
      id=1   Cause            criticality=ignore

    Use case: sim CU subscription registry was wiped (e.g. CU container restart).
    RIC keeps stale sub_id; sending Reset prompts RIC to clear all sub state and
    re-issue RIC_SUB_REQ. Aligns with real OAI behavior (CU restart → E2 Reset).
    """
    rt = _load_runtime()
    pdu_cls = rt.E2AP_PDU_Descriptions.E2AP_PDU

    ie_transaction = {
        "id": _IE_ID_TransactionID,
        "criticality": "reject",
        "value": ("TransactionID", _next_transaction_id()),
    }

    cause_value = ("misc", cause_misc)
    ie_cause = {
        "id": _IE_ID_Cause,
        "criticality": "ignore",
        "value": ("Cause", cause_value),
    }

    reset_request_value = {
        "protocolIEs": [ie_transaction, ie_cause],
    }

    initiating_msg_value = {
        "procedureCode": _PROC_CODE_E2_RESET,
        "criticality": "reject",
        "value": ("ResetRequest", reset_request_value),
    }

    pdu_value = ("initiatingMessage", initiating_msg_value)
    pdu_cls.set_val(pdu_value)
    return pdu_cls.to_aper()


# ── Decoder ──────────────────────────────────────────────────────
def decode_e2ap_pdu(data: bytes) -> dict[str, Any]:
    """Decode raw APER bytes → Python dict."""
    rt = _load_runtime()
    pdu_cls = rt.E2AP_PDU_Descriptions.E2AP_PDU
    pdu_cls.from_aper(data)
    return pdu_cls.get_val()


# ── Self-test (round-trip) ───────────────────────────────────────
def selftest_e2_setup_round_trip() -> dict[str, Any]:
    """Encode a sample E2 Setup Request, decode it back, return summary.

    Used by /Status/read and CI smoke test.
    """
    sample = {
        "global_e2_node_id": {
            "plmn_id": {"mcc": "208", "mnc": "095"},
            "gnb_id": {"value_int": 56, "bit_length": 22, "value_hex": "0x00000038"},
        },
        "ran_functions": [
            {"ran_function_id": 2, "ran_function_oid": "1.3.6.1.4.1.53148.1.2.2.2",
             "ran_function_revision": 1, "service_model": "KPM", "version": "v2.0.03"},
            {"ran_function_id": 3, "ran_function_oid": "1.3.6.1.4.1.53148.1.1.2.3",
             "ran_function_revision": 1, "service_model": "RC", "version": "v01.03"},
        ],
        "expected_ran_name": "gnb_208_095_00000038",
    }
    encoded = encode_e2_setup_request(sample)
    decoded = decode_e2ap_pdu(encoded)
    return {
        "encoded_size": len(encoded),
        "encoded_hex_preview": encoded[:32].hex(),
        "decoded_choice": decoded[0] if isinstance(decoded, tuple) else None,
    }
