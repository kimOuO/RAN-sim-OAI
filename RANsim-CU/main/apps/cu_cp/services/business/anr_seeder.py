"""ANR seeder — 從 CellConfig 種子出初始 NR Cell Relation 表 + CGI 解析表.

開劇本 / F1 Setup 後呼叫:讓每個 active cell 對同 gNB 的其它 active cell 互為鄰區
關係(intra-gNB neighbours),使場景一啟動即有可觀測 / 可操作的 NRT。冪等 —— 已存在
的關係只補齊 target 識別欄位,不覆寫 xApp 改過的 flag / allowed / version。
"""
from __future__ import annotations

import logging

from main.apps.cu_cp.models.cell_config import CellConfig
from main.apps.cu_cp.models.cgi_resolution import CgiResolution
from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
from main.apps.cu_cp.services.common.timestamp_service import TimestampService

logger = logging.getLogger(__name__)


def nr_arfcn_from_ghz(freq_ghz: float) -> int:
    """NR-ARFCN (TS 38.104 §5.4.2.1)。3–24.25 GHz 區間:
    F_REF-Offs=3000 MHz, N_REF-Offs=600000, ΔF_global=15 kHz。
    例:3.45072 GHz → 630048。"""
    f_mhz = freq_ghz * 1000.0
    if f_mhz < 3000.0:  # 0–3 GHz:ΔF=5 kHz, N-Offs=0
        return int(round(f_mhz * 1000.0 / 5.0))
    if f_mhz < 24250.0:
        return int(round(600000 + (f_mhz - 3000.0) * 1000.0 / 15.0))
    # 24.25–100 GHz:ΔF=60 kHz, F-Offs=24250.08 MHz, N-Offs=2016667
    return int(round(2016667 + (f_mhz - 24250.08) * 1000.0 / 60.0))


def seed_from_cells() -> dict:
    """(重)建 intra-gNB 鄰區關係 + CGI 解析。回傳統計。冪等。"""
    now = TimestampService.now()
    cells = list(CellConfig.objects.filter(is_active=True))

    # CGI 解析表:(pci, arfcn) → cell_id
    cgi_created = 0
    for c in cells:
        arfcn = nr_arfcn_from_ghz(c.frequency_ghz)
        _, created = CgiResolution.objects.update_or_create(
            pci=c.pci, arfcn=arfcn,
            defaults={"cgi": c.cell_id, "plmn": c.served_plmn,
                      "created_at": now, "updated_at": now},
        )
        cgi_created += int(created)

    # NR Cell Relation:同 gNB 的其它 active cell 互為鄰區
    rel_created = 0
    for src in cells:
        for tgt in cells:
            if tgt.cell_id == src.cell_id:
                continue
            if tgt.gnb_id != src.gnb_id:
                continue  # M0:先只種同 gNB(intra-gNB)鄰區
            _, created = NrCellRelation.objects.get_or_create(
                source_cell_id=src.cell_id,
                target_cgi=tgt.cell_id,
                defaults={
                    "target_pci": tgt.pci,
                    "target_arfcn": nr_arfcn_from_ghz(tgt.frequency_ghz),
                    "target_rat": "NR",
                    "target_plmn": tgt.served_plmn,
                    "is_ho_allowed": True,
                    "is_remove_allowed": True,
                    "is_xn_allowed": True,
                    "xn_x2_established": True,  # 同 gNB:視為已建立
                    "ho_validated": False,
                    "version": 1,
                    "ho_blocklist": False,
                    "no_remove": False,
                    "xn_blocklist": False,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            rel_created += int(created)

    # 2026-08-12:清 stale 關係 —— source/target 任一不是「當前存在的 cell_id」就刪。
    # 換場景後舊 cell 的關係若不清,xApp 會看到不存在的鄰區(e.g. gnbDT_c0↔c1 殘留)。
    # 只清「兩端都不在現有 cell 集」的孤兒;xApp 手動 ADD 的跨 gNB 關係(target 仍存在)保留。
    valid_ids = set(CellConfig.objects.values_list("cell_id", flat=True))
    stale_qs = NrCellRelation.objects.exclude(
        source_cell_id__in=valid_ids
    ) | NrCellRelation.objects.exclude(target_cgi__in=valid_ids)
    stale_removed = stale_qs.distinct().delete()[0]
    # CGI 解析表同步清 stale
    cgi_removed = CgiResolution.objects.exclude(cgi__in=valid_ids).delete()[0]

    logger.info("ANR seed: %d cells → +%d relations, +%d cgi entries; "
                "-%d stale relations, -%d stale cgi",
                len(cells), rel_created, cgi_created, stale_removed, cgi_removed)
    return {"cells": len(cells), "relations_created": rel_created,
            "cgi_created": cgi_created, "stale_removed": stale_removed}
