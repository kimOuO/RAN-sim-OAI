"""真 F1AP F1SetupRequest 編碼 —— 給 E2nodeComponentConfigAddition 的 requestPart。

為什麼要這支:
    E2AP §9.2.26 規定 e2nodeComponentRequestPart 裝的是**該介面自己的 setup
    訊息原文**;F1 介面就是 F1AP F1 SETUP REQUEST 的 APER bytes。
    先前這裡放的是自訂 TLV(_encode_f1_cells_payload),RIC 照 F1AP 解自然解不到
    Served-Cells-List,R-NIB 就顯示 servedNrCells: 0。

編出來的內容(TS 38.473 §9.2.1.4):
    id=78  TransactionID
    id=42  gNB-DU-ID
    id=45  gNB-DU-Name            (可選,帶上方便 RIC 顯示)
    id=44  gNB-DU-Served-Cells-List
    id=171 GNB-DU-RRC-Version

每個 cell 走 TDD(我們模擬的是 band n78 3.5 GHz TDD);
ARFCN 由 CU 依 TS 38.104 §5.4.2.1 算好帶過來,PRB 數由頻寬 + SCS 查表。

失敗一律回 None,由呼叫端決定要不要退回舊格式 —— 編不出來不該讓 E2 Setup 整個送不出去。
"""
from __future__ import annotations

from typing import Any

from main.utils.logger import get_logger

logger = get_logger(__name__)

# TS 38.101-1 Table 5.3.2-1:SCS 30 kHz 下 頻寬(MHz) → 傳輸 PRB 數
_NRB_BY_BW_SCS30 = {
    10: 24, 15: 38, 20: 51, 25: 65, 30: 78, 40: 106,
    50: 133, 60: 162, 80: 217, 90: 245, 100: 273,
}
_DEFAULT_BAND_NR = 78          # 3.3–3.8 GHz TDD
_RRC_VERSION_LATEST = (0b000, 3)   # latest-RRC-Version BIT STRING(3)


# PrintableString 合法字元(X.680 §41.4)。DU 名稱像 "DU#1" 的 '#' 不在集合內,
# 直接塞會讓整個 PDU 編不出來 —— 濾掉而不是讓 servedNrCells 跟著陪葬。
_PRINTABLE = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 '()+,-./:=?",
)


def _printable(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch in _PRINTABLE)[:150]


def _plmn_bcd(plmn: str) -> bytes:
    """'00101' / '208095' → 3-byte BCD(TS 38.413 PLMN Identity)。"""
    s = (plmn or "00101").strip()
    mcc, mnc = s[:3], s[3:]
    if len(mnc) == 2:
        mnc = mnc + "F"          # 2-digit MNC 補 filler
    d = [int(x, 16) for x in (mcc + mnc)[:6]]
    return bytes([
        d[1] << 4 | d[0],
        d[2] << 4 | d[5],
        d[4] << 4 | d[3],
    ])


def _nrb_for(bandwidth_mhz: float) -> str:
    """頻寬 → NRNRB enum 名。查不到就取最接近的(RIC 只拿來顯示容量)。"""
    bw = int(round(float(bandwidth_mhz or 40)))
    nrb = _NRB_BY_BW_SCS30.get(bw)
    if nrb is None:
        nearest = min(_NRB_BY_BW_SCS30, key=lambda k: abs(k - bw))
        nrb = _NRB_BY_BW_SCS30[nearest]
    return f"nrb{nrb}"


def _served_cell_item(cell: dict[str, Any], nr_cellid: int) -> dict[str, Any]:
    plmn = _plmn_bcd(cell.get("served_plmn") or "")
    arfcn = int(cell.get("arfcn") or 0)
    info: dict[str, Any] = {
        "nRCGI": {
            "pLMN-Identity": plmn,
            # nRCellIdentity 是 BIT STRING(36);pycrate 收 (value, bit_length)
            "nRCellIdentity": (int(nr_cellid) & ((1 << 36) - 1), 36),
        },
        "nRPCI": int(cell.get("pci") or 0),
        "servedPLMNs": [{"pLMN-Identity": plmn}],
        "nR-Mode-Info": ("tDD", {
            "nRFreqInfo": {
                "nRARFCN": arfcn,
                "freqBandListNr": [{"freqBandIndicatorNr": _DEFAULT_BAND_NR,
                                    "supportedSULBandList": []}],
            },
            "transmission-Bandwidth": {
                "nRSCS": "scs30",
                "nRNRB": _nrb_for(cell.get("bandwidth_mhz") or 40),
            },
        }),
        # MIB/SIB1 timing config。我們沒有真的廣播排程,給空字串 ——
        # 欄位是 mandatory,但內容 RIC 不解析。
        "measurementTimingConfiguration": b"",
    }
    tac = int(cell.get("tac") or 0)
    if tac:
        info["fiveGS-TAC"] = tac.to_bytes(3, "big")
    return {"served-Cell-Information": info}


def encode_f1_setup_request(
    gnb_du_id: int,
    cells: list[dict[str, Any]],
    *,
    du_name: str = "",
    nr_cellid_of,
) -> bytes | None:
    """組 F1 SETUP REQUEST 的 APER bytes。編不出來回 None。

    nr_cellid_of(cell) → 36-bit int,沿用既有的 explicit-first / SHA-1 fallback,
    這樣 F1AP 裡的 NR-CGI 跟 KPM indication 裡的是同一個值。
    """
    if not cells:
        return None
    try:
        from pycrate_asn1dir import F1AP
    except ImportError:
        logger.warning("pycrate F1AP 不可用,F1 component 退回舊格式")
        return None

    try:
        items = []
        for c in cells:
            items.append({
                "id": 43,                       # id-GNB-DU-Served-Cells-Item
                "criticality": "reject",
                "value": ("GNB-DU-Served-Cells-Item", _served_cell_item(c, nr_cellid_of(c))),
            })

        ies = [
            {"id": 78, "criticality": "reject", "value": ("TransactionID", 0)},
            {"id": 42, "criticality": "reject", "value": ("GNB-DU-ID", int(gnb_du_id))},
        ]
        if _printable(du_name):
            ies.append({"id": 45, "criticality": "ignore",
                        "value": ("GNB-DU-Name", _printable(du_name))})
        ies.append({"id": 44, "criticality": "reject",
                    "value": ("GNB-DU-Served-Cells-List", items)})
        ies.append({"id": 171, "criticality": "reject",
                    "value": ("RRC-Version", {"latest-RRC-Version": _RRC_VERSION_LATEST})})

        pdu = F1AP.F1AP_PDU_Descriptions.F1AP_PDU
        pdu.set_val(("initiatingMessage", {
            "procedureCode": 1,                 # id-F1Setup
            "criticality": "reject",
            "value": ("F1SetupRequest", {"protocolIEs": ies}),
        }))
        return pdu.to_aper()
    except Exception:  # noqa: BLE001
        logger.exception("F1SetupRequest 編碼失敗 (gnb_du_id=%s, %d cells)", gnb_du_id, len(cells))
        return None
