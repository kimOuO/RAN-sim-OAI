"""場域的 E2 識別 —— gNB ID / E2 node 名(meid)/ 每個 cell 的 NR Cell Identity。

為什麼要能「在啟動前算出來」:外部 Agent 讀完場域配置後,會依這些識別**部署 xApp 到 RIC**
(E2 訂閱與 RICcontrolRequest 都用 meid + NCI 定位)。識別若要等啟動才確定,xApp 就訂不到。
場景的 `e2_slot` 把槽位釘住,這裡就能事先推導出與執行期完全相同的值。

槽位 → gNB ID → E2 node 名沿用 container_spawner(同一份,不重複實作)。
NCI 這條規則目前散在三處,任何一處改動三處都要一起改:
    - e2adapter  e2ap_codec._hash_nr_cell_id     (送 E2 的值)
    - CU         e2_control_actor.compute_nr_cell_id(解析 control target 的值)
    - 本檔                                        (對外宣告的值)
三者不一致的後果是 xApp 下的 control 打不中 cell(F1 送 NCI_A、CU 算 NCI_B 那類事故),
所以 tests/ 有一個把已知常數釘死的回歸測試。
"""
from __future__ import annotations

import hashlib

from main.apps.run_lifecycle.services.optional.container_spawner import (
    GNB_ID_SLOTS,
    e2_node_name,
    gnb_id_hex_for_slot,
)

NCI_BITS = 36
TAG_SEP = ":"


def cell_tag_for(gnb_id_hex: str) -> str:
    """gNB ID → cell 標籤(低 12 bit),例 0x000e01 → "e01"(與 cell_tag.tag_cell 同源)。"""
    return f"{int(gnb_id_hex, 16) & 0xfff:03x}"


def tag_cell(tag: str, name: str) -> str:
    if not tag or not name or TAG_SEP in name:
        return name
    return f"{tag}{TAG_SEP}{name}"


def nr_cell_identity(cell_id: str, explicit: int | None = None) -> int:
    """36-bit NR Cell Identity。有 explicit 用 explicit,否則 SHA-1 前 5 byte 截 36 bit。"""
    mask = (1 << NCI_BITS) - 1
    if explicit is not None:
        return int(explicit) & mask
    h = hashlib.sha1((cell_id or "").encode("utf-8")).digest()
    return int.from_bytes(h[:5], "big") & mask


def field_e2_identity(slot: int, cell_names: list[str], *, mcc: str = "208", mnc: str = "95",
                      explicit_nci: dict[str, int] | None = None) -> dict:
    """場域的完整 E2 識別,給 Agent 介面 I-2 / I-3 回報。

    cell_names 是 registry 的 cell 名稱(未加標籤);回傳每個 cell 對外的
    cell_id(含槽位標籤)與 NCI —— xApp 訂閱與下令要用的就是這兩個。
    """
    if not 1 <= int(slot) <= GNB_ID_SLOTS:
        raise ValueError(f"e2_slot 必須在 1~{GNB_ID_SLOTS},拿到 {slot}")
    gnb_id_hex = gnb_id_hex_for_slot(int(slot))
    tag = cell_tag_for(gnb_id_hex)
    plmn = f"{mcc}{str(mnc).zfill(3)}"
    cells = []
    for name in cell_names:
        cid = tag_cell(tag, name)
        nci = nr_cell_identity(cid, (explicit_nci or {}).get(name))
        cells.append({
            "name": name,
            "cell_id": cid,
            "nr_cell_identity": nci,
            "nr_cell_identity_hex": f"0x{nci:09x}",
            "ncgi": f"{plmn}-{nci:09x}",
        })
    return {
        "slot": int(slot),
        "gnb_id": gnb_id_hex,
        "gnb_id_int": int(gnb_id_hex, 16),
        "e2_node_id": e2_node_name(gnb_id_hex, mcc, mnc),
        "plmn": {"mcc": mcc, "mnc": str(mnc).zfill(3)},
        "cell_tag": tag,
        "cells": cells,
    }
