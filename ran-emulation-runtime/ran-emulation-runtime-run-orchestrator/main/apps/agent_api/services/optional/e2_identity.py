"""場域的 E2 識別 —— 每個 gNB 一個 E2 node(多 gNB 改版,介面 C13)。

為什麼要能「在啟動前算出來」:外部 Agent 讀完場域配置後,會依這些識別**部署 xApp 到 RIC**
(E2 訂閱與 RICcontrolRequest 都用 meid + NCI 定位)。識別若要等啟動才確定,xApp 就訂不到。
場景的 `e2_block` 把區塊釘住,這裡就能事先推導出與執行期完全相同的值。

規則只有一份:ran_sim_protocol.run_topology(內部用 e2_identity)。orchestrator 開場組拓樸、
CU / DU / UE / e2adapter 執行期查的都是它 —— 這裡直接呼叫同一個 build_from_tree,不另寫推導。
"""
from __future__ import annotations

from typing import Any

from ran_sim_protocol import e2_identity as ident
from ran_sim_protocol.cell_tag import TAG_SEP, strip_tag, tag_cell  # noqa: F401 — 其他模組由此取用
from ran_sim_protocol.run_topology import build_from_tree

# 只用來算識別,不會真的起容器;run id 影響的只有主機名,不出現在回傳裡
_PREVIEW_RUN = "agent-preview-000000000000"


def field_e2_identities(tree: dict, block: int) -> list[dict[str, Any]]:
    """場域在區塊 `block` 下每個 gNB 的 E2 識別(I-1 / I-2 的 e2_identities[])。

    每個 cell 帶:registry 名稱(name)、執行期名稱(cell_id,帶 gNB 前綴)、所屬 E2 node(ran_name)、
    NCI(整數與十六進位)、ncgi(D2 固定格式)。
    """
    if not ident.BLOCK_MIN <= int(block) <= ident.BLOCK_MAX:
        raise ValueError(f"e2_block 必須在 {ident.BLOCK_MIN}~{ident.BLOCK_MAX},拿到 {block}")
    topo = build_from_tree(tree, run_uuid=_PREVIEW_RUN, block=int(block), e2_port_base=0)
    out = []
    for g in topo.gnbs:
        out.append({
            "node_id": g.name,
            "e2_index": g.e2_index,
            "slot": ident.slot_for(int(block), g.e2_index),
            "gnb_id": g.gnb_id_hex,
            "gnb_id_int": g.gnb_id,
            "gnb_id_bits": g.gnb_id_bits,
            "e2_node_id": g.meid,
            "meid": g.meid,
            "plmn": {"mcc": g.mcc, "mnc": g.mnc.zfill(3), "bcd": g.plmn_bcd},
            "cell_tag": g.cell_tag,
            "cells": [{
                "name": c.name,
                "cell_id": c.cell_id,
                "ran_name": g.meid,
                "nr_cell_identity": c.nci,
                "nr_cell_identity_hex": f"0x{c.nci:09x}",
                "ncgi": c.ncgi,
                "local_cell_id": c.local_cell_id,
            } for d in g.dus for c in d.cells],
        })
    return out


def cells_by_name(identities: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """registry cell 名稱 → cell 識別(附所屬 node)。名稱在場域內重複時取第一個出現的。"""
    out: dict[str, dict[str, Any]] = {}
    for n in identities:
        for c in n["cells"]:
            out.setdefault(c["name"], {**c, "node_id": n["node_id"], "meid": n["meid"], "gnb_id": n["gnb_id"]})
    return out
