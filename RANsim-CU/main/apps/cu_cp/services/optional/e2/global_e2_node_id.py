"""GlobalE2node-ID composer — sim 啟動時宣告自身為 gNB 的 ID。

對應 O-RAN E2AP v2.0.3 §9.1.1.5 GlobalE2node-ID:
  global-gNB-ID:
    plmn-id: TBCD(MCC + MNC)  → 3 bytes
    gnb-id:  BIT STRING SIZE(22..32)

E2 adapter container 在 E2 Setup Request 階段呼叫 sim CU 的 /E2NodeId/read
拿到這些值後 PER-encode 進 globalE2node-ID 欄位。

OAI ref:
  - openair2/E2AP/RAN_FUNCTION/init_ran_func.c::e2ap_send_setup_request()
"""
from __future__ import annotations

from main.utils.env_loader import get_int, get_str


# 預設值與 backend_rule.md / RIC 約定對齊（見 conversation history）：
# - MCC=208, MNC=95（兩碼 → 補零成 095）
# - gnb-id 22-bit 0x000038
# - ranFunctionId KPM=2, RC=3（O-RAN convention）
_DEFAULT_MCC = "208"
_DEFAULT_MNC = "95"
# 2026-05-16: 對齊 OAI gNB_ID 值 0xe00 = 3584。E2AP ASN.1 強制 BIT STRING SIZE(22..32),
# 所以 wire format 是 22-bit (0x000e00),value 與 OAI 12-bit 0xe00 相同。
_DEFAULT_GNB_ID_HEX = "0x000e00"
_DEFAULT_GNB_ID_LENGTH = 22
_DEFAULT_RAN_FUNC_ID_KPM = 2
_DEFAULT_RAN_FUNC_ID_RC = 3
_DEFAULT_KPM_OID = "1.3.6.1.4.1.53148.1.2.2.2"  # E2SM-KPM v2.0.03
_DEFAULT_RC_OID = "1.3.6.1.4.1.53148.1.1.2.3"   # E2SM-RC  v01.03
_DEFAULT_RAN_FUNC_ID_CCC = 4
_DEFAULT_CCC_OID = "1.3.6.1.4.1.53148.1.1.2.4"  # E2SM-CCC (cell on/off / energy saving)
# 2026-05-16: TAC / SST env shells — 接口存在但邏輯未實作。
# 對齊 OAI tracking_area_code=0xa000、snssaiList.sst=1。
_DEFAULT_TAC = 0xa000
_DEFAULT_SST = 1


def _normalize_mnc(mnc: str) -> str:
    """MNC 補零到 3 碼（O-RAN spec 要求 PLMN MNC 是 3 digits）。"""
    return mnc.zfill(3) if len(mnc) < 3 else mnc


def _gnb_id_to_int(gnb_id_hex: str) -> int:
    """支援 '0x000038' / '38' / '0x38' 多種格式輸入。"""
    s = gnb_id_hex.strip().lower()
    if s.startswith("0x"):
        return int(s, 16)
    return int(s, 16)  # 預設都當 hex


def _read_du_components() -> list[dict]:
    """List F1-served DUs and their cells for E2nodeComponentConfigAddition.

    R1 alignment: E2 Setup 必須宣告 NG + F1 component。F1 帶 served-cells，
    每個 cell 有 NR-CGI / PCI / TAC / served PLMN, 給 RIC R-NIB 寫 cell-level
    routing key。沒這個, RIC 只能拿 globalE2node-ID 路 control, 無法做 per-cell
    的 RC.action (e.g., handover target_cgi)。
    """
    # Lazy import 避免 Django app registry 在 module-load 階段未 ready
    from main.apps.cu_cp.models import CellConfig, DuRegistry

    # TAC / SST 走 env (P3.2 / P3.3 空殼接口 — 邏輯未實作,只是讓 PDU 帶上正確值)
    tac = get_int("SERVED_TAC", _DEFAULT_TAC)
    sst = get_int("SST", _DEFAULT_SST)

    components: list[dict] = []
    for du in DuRegistry.objects.all().order_by("gnb_du_id"):
        cells = CellConfig.objects.filter(served_by_du_id=du.gnb_du_id).order_by("cell_id")
        cell_list = []
        for c in cells:
            cell_list.append({
                "cell_id": c.cell_id,
                "nr_cell_id": c.cell_id,    # legacy: encoder hash 的輸入(平台 ID)
                # P2.6: explicit nr_cellid 整數 (OAI 真值, e.g. 12345678),encoder 優先用
                "nr_cellid": getattr(c, "nr_cellid", None),
                "pci": c.pci,
                "tac": tac,
                "served_plmn": c.served_plmn,
                "s_nssai": {"sst": sst},
                "is_active": c.is_active,
            })
        if not cell_list:
            continue
        components.append({
            "interface_type": "f1",
            "gnb_du_id": du.gnb_du_id,
            "du_name": du.name,
            "cells": cell_list,
        })
    return components


def read_global_e2_node_id() -> dict:
    """組 globalE2node-ID payload + RAN function inventory + F1 component cells。

    Adapter 不需自己拼 OID/格式，sim 直接給最終 ASN.1-friendly 結構即可。
    """
    mcc = get_str("PLMN_MCC", _DEFAULT_MCC)
    mnc_raw = get_str("PLMN_MNC", _DEFAULT_MNC)
    # 保留原始 MNC 長度給 adapter 編 PLMN BCD（2-digit 用 0xF filler，3-digit 不用）
    mnc_digit_count = len(mnc_raw)
    mnc_padded = _normalize_mnc(mnc_raw)
    gnb_id_hex = get_str("GNB_ID_HEX", _DEFAULT_GNB_ID_HEX)
    gnb_id_length = get_int("GNB_ID_LENGTH", _DEFAULT_GNB_ID_LENGTH)
    gnb_id_int = _gnb_id_to_int(gnb_id_hex)

    kpm_id = get_int("RAN_FUNC_ID_KPM", _DEFAULT_RAN_FUNC_ID_KPM)
    rc_id = get_int("RAN_FUNC_ID_RC", _DEFAULT_RAN_FUNC_ID_RC)

    # R-NIB ranName 格式：gnb_<MCC>_<MNC_padded>_<gnb_id_hex>
    # gnb_id hex 寬度 = ceil(bit_length / 4)：22-bit → 6 hex；32-bit → 8 hex
    hex_width = (gnb_id_length + 3) // 4
    ran_name = f"gnb_{mcc}_{mnc_padded}_{gnb_id_int:0{hex_width}x}"

    return {
        "global_e2_node_id": {
            "plmn_id": {
                "mcc": mcc,
                "mnc": mnc_padded,
                "mnc_digit_count": mnc_digit_count,   # 給 adapter 決定 BCD encoding
            },
            "gnb_id": {
                "value_hex": f"0x{gnb_id_int:08x}",
                "value_int": gnb_id_int,
                "bit_length": gnb_id_length,
            },
        },
        "ran_functions": [
            {
                "ran_function_id": kpm_id,
                "ran_function_oid": _DEFAULT_KPM_OID,
                "ran_function_revision": 1,
                "service_model": "KPM",
                "version": "v2.0.03",
            },
            {
                "ran_function_id": rc_id,
                "ran_function_oid": _DEFAULT_RC_OID,
                "ran_function_revision": 1,
                "service_model": "RC",
                "version": "v01.03",
            },
            {
                # E2SM-CCC(cell 開關/節能)。adapter 端由 E2SM_CCC_ENABLE gate 是否廣播;
                # 預設關 → 不進 E2 Setup,不影響 KPM/RC 對 RIC 註冊。
                "ran_function_id": _DEFAULT_RAN_FUNC_ID_CCC,
                "ran_function_oid": _DEFAULT_CCC_OID,
                "ran_function_revision": 1,
                "service_model": "CCC",
                "version": "v04.00",
            },
        ],
        "components": _read_du_components(),
        "expected_ran_name": ran_name,
    }
