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
    recorded_at = models.DateTimeField(db_index=True)

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_cell_measurement_log"
        ordering = ("-recorded_at",)
