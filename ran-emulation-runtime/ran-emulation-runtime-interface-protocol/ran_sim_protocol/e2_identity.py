"""E2 身分規則 —— 全平台唯一的真值來源(2026-09-27 多 gNB 改版)。

一個場景的每個 gNB 各是一個 E2 node。以下規則在 orchestrator(開場前宣告給 Agent / RIC)、
UE 容器(組 cell 設定)、CU(E2 Setup、控制解析、Xn 路由)、e2adapter(編碼)共用;
任何一處自行計算都會讓 xApp 下的控制打不中 cell,所以一律 import 本模組。
規格:docs/architecture/multi_gnb_plan.md D2、D3(RIC 端 anr_xapps 已確認)。

區塊與槽位(D3)
--------------
    槽位      = 16 · block + e2_index          block 1–15、e2_index 0–15
    gNB ID    = 0x000e00 | 槽位                 22 bit
    meid      = gnb_<mcc>_<mnc 三位>_<gNB ID 六位十六進位>   例 gnb_208_095_000e31
    cell 前綴 = gNB ID 低 12 bit 的三位十六進位             例 e31 → cell 名 e31:src
block 0(e00)保留給 RIC 常駐 xApp;block ≥ 16 會讓 gNB ID 進位成 0xf00,命名不一致,故上限 15。

NCI 與 NCGI(D2,TS 38.300 §8.2)
-------------------------------
    NCI  = gNB ID(22 bit)‖ 本地 cell ID(14 bit)            36 bit
    NCGI = <PLMN 六位>-<NCI 九位小寫十六進位,零填補>        例 208095-0038c4000(gNB 0xe31、本地 cell 0)← 雙方以字串比對
由 NCI 取高 22 bit 即得所屬 gNB,Xn 路由與 RIC 都靠這個關係。
"""
from __future__ import annotations

from ran_sim_protocol.cell_tag import TAG_SEP, strip_tag, tag_cell, tag_of

__all__ = [
    "BLOCK_SIZE", "BLOCK_MIN", "BLOCK_MAX", "GNB_ID_BASE", "GNB_ID_BITS", "LOCAL_CELL_BITS", "NCI_BITS",
    "slot_for", "gnb_id_for", "gnb_id_hex", "meid", "cell_tag", "nci", "ncgi", "parse_ncgi",
    "gnb_id_of_nci", "local_cell_of_nci", "plmn_bcd_hex", "gnb_id_bits", "block_of_slot",
    "node_identity", "TAG_SEP", "tag_cell", "strip_tag", "tag_of",
]

BLOCK_SIZE = 16
BLOCK_MIN = 1
BLOCK_MAX = 15
GNB_ID_BASE = 0x000E00
GNB_ID_BITS = 22
LOCAL_CELL_BITS = 14
NCI_BITS = 36
_GNB_MASK = (1 << GNB_ID_BITS) - 1
_LOCAL_MASK = (1 << LOCAL_CELL_BITS) - 1
_NCI_MASK = (1 << NCI_BITS) - 1


def slot_for(block: int, e2_index: int) -> int:
    """場景區塊 + gNB 序號 → 槽位。越界直接拋錯(不默默截斷,否則會與別的場景撞號)。"""
    b, i = int(block), int(e2_index)
    if not BLOCK_MIN <= b <= BLOCK_MAX:
        raise ValueError(f"E2 區塊必須在 {BLOCK_MIN}–{BLOCK_MAX},拿到 {b}")
    if not 0 <= i < BLOCK_SIZE:
        raise ValueError(f"gNB e2_index 必須在 0–{BLOCK_SIZE - 1},拿到 {i}")
    return BLOCK_SIZE * b + i


def block_of_slot(slot: int) -> int:
    return int(slot) // BLOCK_SIZE


def gnb_id_for(block: int, e2_index: int) -> int:
    return (GNB_ID_BASE | slot_for(block, e2_index)) & _GNB_MASK


def gnb_id_hex(gnb_id: int) -> str:
    return f"0x{int(gnb_id) & _GNB_MASK:06x}"


def meid(gnb_id: int, mcc: str = "208", mnc: str = "95") -> str:
    return f"gnb_{mcc}_{str(mnc).zfill(3)}_{int(gnb_id) & _GNB_MASK:06x}"


def cell_tag(gnb_id: int) -> str:
    return f"{int(gnb_id) & 0xFFF:03x}"


def nci(gnb_id: int, local_cell_id: int) -> int:
    lc = int(local_cell_id)
    if not 0 <= lc <= _LOCAL_MASK:
        raise ValueError(f"本地 cell ID 必須在 0–{_LOCAL_MASK},拿到 {lc}")
    return (((int(gnb_id) & _GNB_MASK) << LOCAL_CELL_BITS) | lc) & _NCI_MASK


def gnb_id_of_nci(value: int) -> int:
    return (int(value) & _NCI_MASK) >> LOCAL_CELL_BITS


def local_cell_of_nci(value: int) -> int:
    return int(value) & _LOCAL_MASK


def ncgi(value: int, mcc: str = "208", mnc: str = "95") -> str:
    """固定格式 <mcc><mnc 三位>-<NCI 九位小寫十六進位>(RIC 以字串比對,格式不可變)。"""
    return f"{mcc}{str(mnc).zfill(3)}-{int(value) & _NCI_MASK:09x}"


def parse_ncgi(text: str) -> tuple[str, int] | None:
    """"208095-0038c4000" → ("208095", 0x0038c4000);格式不符回 None。"""
    if not text or "-" not in text:
        return None
    plmn, hexpart = text.split("-", 1)
    if len(plmn) != 6 or not plmn.isdigit():
        return None
    try:
        return plmn, int(hexpart, 16) & _NCI_MASK
    except ValueError:
        return None


def plmn_bcd_hex(mcc: str = "208", mnc: str = "95") -> str:
    """TS 38.413 PLMN Identity 的 BCD 三 byte(RIC 閘道 register 的 plmn 欄),例 208/95 → 02F859。"""
    m, n = str(mcc), str(mnc)
    d = [int(x) for x in m]
    if len(n) == 2:
        n1, n2, n3 = 0xF, int(n[0]), int(n[1])
    else:
        n1, n2, n3 = int(n[2]), int(n[0]), int(n[1])
    b0 = (d[1] << 4) | d[0]
    b1 = (n1 << 4) | d[2]
    b2 = (n3 << 4) | n2
    return f"{b0:02X}{b1:02X}{b2:02X}"


def gnb_id_bits(gnb_id: int) -> str:
    return format(int(gnb_id) & _GNB_MASK, f"0{GNB_ID_BITS}b")


def node_identity(block: int, e2_index: int, node_id: str, mcc: str = "208", mnc: str = "95") -> dict:
    """一個 gNB 的完整 E2 身分(orchestrator 寫進 scene_run.e2_nodes、送 RIC 閘道 register 用)。"""
    gid = gnb_id_for(block, e2_index)
    return {
        "node_id": node_id,
        "e2_index": int(e2_index),
        "slot": slot_for(block, e2_index),
        "gnb_id": gid,
        "gnb_id_hex": gnb_id_hex(gid),
        "meid": meid(gid, mcc, mnc),
        "cell_tag": cell_tag(gid),
        "plmn_mcc": str(mcc),
        "plmn_mnc": str(mnc),
        "plmn_bcd": plmn_bcd_hex(mcc, mnc),
        "gnb_id_bits": gnb_id_bits(gid),
    }
