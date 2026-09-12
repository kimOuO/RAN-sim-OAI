"""Centralised platform_cell_id (str) ↔ nr_cellid (36-bit int) mapping.

2026-05-16 P2.5 — 對應 alignment_action_plan.md。

Resolution order(優先用 explicit OAI 真值,沒有再 fallback SHA-1 hash):
  1. CellConfig.nr_cellid 欄位(來自 scene_config 顯式設定)
  2. SHA-1(cell_id)[:5] mod (1<<36) — deterministic 隨機分布,collision <1e-7

Reverse lookup:
  - 先用 CellConfig.objects.filter(nr_cellid=...) 做精確比對
  - 沒命中再退回 hash 線性掃(只對沒填 nr_cellid 的 cell 有效)
"""
from __future__ import annotations

import hashlib


_NR_CELL_ID_MASK = (1 << 36) - 1


def hash_cell_id(cell_id: str) -> int:
    """SHA-1 截 36-bit。"""
    h = hashlib.sha1((cell_id or "").encode("utf-8")).digest()
    return int.from_bytes(h[:5], "big") & _NR_CELL_ID_MASK


def to_nr_cellid(cell_id: str, explicit: int | None = None) -> int:
    """platform cell_id (str) → 36-bit nr_cellid (int).

    有 explicit 就直接用(會 mask 進 36-bit 範圍),否則 SHA-1 hash。
    """
    if explicit is not None:
        return int(explicit) & _NR_CELL_ID_MASK
    return hash_cell_id(cell_id)


def to_platform_cell_id(nr_cellid: int) -> str | None:
    """36-bit nr_cellid (int) → platform cell_id (str)。

    優先精確比對 DB 欄位,沒命中退回 hash 反查(較慢)。
    沒找到回 None。
    """
    target = int(nr_cellid) & _NR_CELL_ID_MASK

    # Lazy import 避免 Django app registry 未 ready 就 import 模型
    from main.apps.cu_cp.models import CellConfig

    explicit_match = (
        CellConfig.objects.filter(nr_cellid=target).only("cell_id").first()
    )
    if explicit_match:
        return explicit_match.cell_id

    for c in CellConfig.objects.only("cell_id", "nr_cellid"):
        if c.nr_cellid is not None:
            continue
        if hash_cell_id(c.cell_id) == target:
            return c.cell_id
    return None
