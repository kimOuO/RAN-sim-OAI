"""把 MAC 排程結果組成 DlTtiRequest / UlTtiRequest。

Inputs(來自 mac):
  - rb_alloc: {ue_id: prb_count}
  - mcs_map: {ue_id: mcs_int}
  - pmi_map: {ue_id: int}
  - rank_map: {ue_id: int}
  - tbs_map: {ue_id: payload_bytes}
  - harq_map: {ue_id: harq_pid}
"""
from __future__ import annotations

from ran_sim_protocol.fapi import DlPduConfig, DlTtiRequest, UlPduConfig, UlTtiRequest


def build_dl_tti(
    *,
    sfn: int,
    slot: int,
    rb_alloc: dict[str, int],
    mcs_map: dict[str, int],
    pmi_map: dict[str, int] | None = None,
    rank_map: dict[str, int] | None = None,
    tbs_map: dict[str, int] | None = None,
    harq_map: dict[str, int] | None = None,
) -> DlTtiRequest:
    pmi_map = pmi_map or {}
    rank_map = rank_map or {}
    tbs_map = tbs_map or {}
    harq_map = harq_map or {}

    pdus: list[DlPduConfig] = []
    prb_cursor = 0
    for ue_id, prb_count in rb_alloc.items():
        if prb_count <= 0:
            continue
        pdus.append(
            DlPduConfig(
                ue_id=ue_id,
                prb_start=prb_cursor,
                prb_count=prb_count,
                mcs=mcs_map.get(ue_id, 9),
                layers=rank_map.get(ue_id, 1),
                pmi=pmi_map.get(ue_id, 0),
                payload_size_bytes=tbs_map.get(ue_id, 0),
                harq_pid=harq_map.get(ue_id, 0),
            ),
        )
        prb_cursor += prb_count
    return DlTtiRequest(sfn=sfn, slot=slot, pdus=pdus)


def build_ul_tti(
    *,
    sfn: int,
    slot: int,
    ul_alloc: dict[str, int],
    mcs_map: dict[str, int],
    rank_map: dict[str, int] | None = None,
    harq_map: dict[str, int] | None = None,
) -> UlTtiRequest:
    rank_map = rank_map or {}
    harq_map = harq_map or {}
    pdus: list[UlPduConfig] = []
    prb_cursor = 0
    for ue_id, prb_count in ul_alloc.items():
        if prb_count <= 0:
            continue
        pdus.append(
            UlPduConfig(
                ue_id=ue_id,
                prb_start=prb_cursor,
                prb_count=prb_count,
                mcs=mcs_map.get(ue_id, 9),
                layers=rank_map.get(ue_id, 1),
                harq_pid=harq_map.get(ue_id, 0),
            ),
        )
        prb_cursor += prb_count
    return UlTtiRequest(sfn=sfn, slot=slot, pdus=pdus)
