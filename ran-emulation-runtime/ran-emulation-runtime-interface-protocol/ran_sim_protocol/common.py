"""Common dataclass shared across F1AP / FAPI / NGAP / E1AP / Physics."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _default_plmn() -> str:
    # 從 env 組 served_plmn,避免散落各處硬編 "00101"。
    # 沒設 env 時 fallback 到 3GPP 測試 PLMN "00101"。
    mcc = os.environ.get("PLMN_MCC", "001")
    mnc = os.environ.get("PLMN_MNC", "01")
    return f"{mcc}{mnc}"


@dataclass
class CellConfig:
    cell_id: str
    pci: int
    frequency_ghz: float
    bandwidth_mhz: float
    served_plmn: str = field(default_factory=_default_plmn)
    gnb_id: str = ""
    is_active: bool = True
    # OAI 真實 nr_cellid (36-bit int) 對齊用;空值時走 SHA-1 hash fallback。
    nr_cellid: int | None = None
    # 2026-09-22: 每 cell 發射功率 (dBm)。來源是場景的 gNB/cell 設定,
    # 原本只有 RU 拿得到 (RU 直接讀 Cell DB);CU 端要算 TS 28.552 PEE.AvgPower
    # 就必須把它一路帶上來。None = 沒設定,PEE 欄位就不輸出(不要猜)。
    tx_power_dbm: float | None = None


@dataclass
class DrbConfig:
    drb_id: int
    qos_5qi: int
    rlc_mode: str = "AM"  # "AM" | "UM" | "TM"


@dataclass
class NeighborMeas:
    # cell_id 是模擬器的「上帝視角」—— 真實 UE 量測鄰區只讀得到 PCI 與載波頻率,
    # 要知道對方是誰得另外叫 UE 去讀它的 SIB1(CGI 解析)。保留它是為了讓 CGI 解析
    # 程序有真值可回,以及維持既有 ANR 的比對;對外分析應以 pci + arfcn 為準。
    cell_id: str
    rsrp_dbm: float
    rsrq_db: float | None
    # 2026-09-22:UE 真實看得到的兩個識別。None = 舊版 DU 沒帶。
    # 缺了這兩個,「缺漏鄰區」「PCI 混淆」這類判斷在對外資料上做不出來。
    pci: int | None = None
    arfcn: int | None = None


@dataclass
class AntennaArrayConfig:
    rows: int
    cols: int
    polarization: str = "V"  # "V" | "H" | "VH" | "cross"
    pattern: str = "tr38901"  # "tr38901" | "dipole" | "iso" | "hw_dipole" | "vh_dipole"
    vertical_spacing: float = 0.5
    horizontal_spacing: float = 0.5
