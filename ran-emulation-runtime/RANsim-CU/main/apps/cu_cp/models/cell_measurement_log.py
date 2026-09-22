"""CellMeasurementLog — cell-level KPI (AL2, 對齊 3GPP TS 28.552 RRU.PrbTotDl).

Cell-level metric 不從 per-UE rb_width_dl 加總, 直接由 DU pm_aggregator
cell-level accumulator 算 (avg over window ticks). 避免 UE 樣本不齊造成 >100%.
"""
from __future__ import annotations

from django.db import models


class CellMeasurementLog(models.Model):
    id = models.AutoField(primary_key=True)
    cell_id = models.CharField(max_length=64, db_index=True)
    prb_pct_dl = models.FloatField(default=0.0)  # 0~100
    prb_pct_ul = models.FloatField(default=0.0)
    tick_count = models.IntegerField(default=0)
    window_seconds = models.FloatField(default=0.0)
    # 與 per-UE 報告同一個 PM 視窗序號:歸檔照它把 cell 與 UE 併到同一列
    window_seq = models.IntegerField(null=True, blank=True, db_index=True)
    # 視窗結束時掛在本 cell 的 UE 數(見 f1ap.GnbDuCellMeasurementReport.connected_ues)。
    # null = 舊版 DU 沒帶,歸檔退回舊行為。
    connected_ues = models.IntegerField(null=True, blank=True)
    # 2026-09-22:劇本時鐘(DU 的 scene_tick × sim_dt_ms)。null = 舊版 DU 沒帶,
    # 歸檔退回原本的 tick 累加推算。
    scene_sim_ms = models.BigIntegerField(null=True, blank=True)
    recorded_at = models.DateTimeField(db_index=True)

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_cell_measurement_log"
        ordering = ("-recorded_at",)
