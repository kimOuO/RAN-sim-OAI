"""DL slot grid descriptor — 把 DlTtiRequest 的 PDU 拼成 grid 描述（不真排 RE）。

對 OAI: nr_feptx_tp 的 input grid 概念。
"""
from __future__ import annotations

from typing import Any

from ran_sim_protocol.fapi import DlTtiRequest


def build_dl_grid(req: DlTtiRequest) -> dict[str, Any]:
    """回傳 {sfn, slot, prb_alloc:[{ue_id, prb_start, prb_count, mcs, layers, pmi}]}。"""
    prb_alloc = [
        {
            "ue_id": p.ue_id,
            "prb_start": p.prb_start,
            "prb_count": p.prb_count,
            "mcs": p.mcs,
            "layers": p.layers,
            "pmi": p.pmi,
            "harq_pid": p.harq_pid,
        }
        for p in req.pdus
    ]
    total_prb = sum(p["prb_count"] for p in prb_alloc)
    return {
        "sfn": req.sfn,
        "slot": req.slot,
        "prb_alloc": prb_alloc,
        "total_prb_used": total_prb,
        "ue_count": len({p["ue_id"] for p in prb_alloc}),
    }
