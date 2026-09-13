"""Run 唯一的 cell 識別碼標籤(2026-09-13,回應 RIC 端「ncgi 跨場景要唯一」)。

多場景並行時,RIC/xApp 以 cell 字串(src / dst / ncgi)當狀態鍵,不同場景若都叫 s25_c0 就會互相吃掉。
所以 sim 對外的 cell_id 一律是 "<tag>:<name>",tag = 該 run 的 gNB ID 低 12 bit(例 "e01"),
與 RIC 看到的 E2 node(gnb_208_095_000e01)同源,天然唯一。

- 加標籤:只在 UE driver 的 scenario loader(所有 cell 字串的唯一源頭)做,env CELL_ID_TAG 由 orchestrator 設。
- 剝標籤:只在「cell → 物理 tx 名(npz / Sionna 的 gnb#pci)」的轉換點做(DU channel_cache_du、RU payload_builder、UE cell_selection)。
- 其他地方(DU/CU/E2/KPM 封存/監控)一律原樣傳遞,不解析。
"""
from __future__ import annotations

TAG_SEP = ":"


def tag_cell(tag: str, name: str) -> str:
    """加標籤;tag 空或 name 已帶標籤就原樣回。"""
    if not tag or not name or TAG_SEP in name:
        return name
    return f"{tag}{TAG_SEP}{name}"


def strip_tag(cell_id: str) -> str:
    """去掉 "<tag>:" 前綴;沒有就原樣回。"""
    if cell_id and TAG_SEP in cell_id:
        return cell_id.split(TAG_SEP, 1)[1]
    return cell_id


def tag_of(cell_id: str) -> str:
    return cell_id.split(TAG_SEP, 1)[0] if cell_id and TAG_SEP in cell_id else ""
