"""Run 唯一 cell 標籤 helper — 與 ran_sim_protocol.cell_tag 同語意(UE image 沒掛 protocol 套件,所以本地一份)。
cell_id = "<tag>:<name>",tag = run 的 gNB ID 低 12 bit(orchestrator env CELL_ID_TAG,例 "e01")。"""
from __future__ import annotations

TAG_SEP = ":"


def tag_cell(tag: str, name: str) -> str:
    if not tag or not name or TAG_SEP in name:
        return name
    return f"{tag}{TAG_SEP}{name}"


def strip_tag(cell_id: str) -> str:
    if cell_id and TAG_SEP in cell_id:
        return cell_id.split(TAG_SEP, 1)[1]
    return cell_id
