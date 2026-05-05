"""MeasurementLog — sliding-window record of GnbDuMeasurementReport.

Used by E2KPM aggregator and by A3 algorithm (last-state lookup).
"""
from __future__ import annotations

from django.db import models


class MeasurementLog(models.Model):
    id = models.AutoField(primary_key=True)
    meas_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    ue_id = models.CharField(max_length=64, db_index=True)
    rsrp_dbm = models.FloatField()
    sinr_db = models.FloatField()
    throughput_dl_mbps = models.FloatField(default=0.0)
    throughput_ul_mbps = models.FloatField(default=0.0)
    mcs_dl = models.IntegerField(default=0)
    rb_width_dl = models.IntegerField(default=0)
    mimo_rank = models.IntegerField(default=1)
    neighbor_cells_json = models.JSONField(default=list)

    recorded_at = models.DateTimeField(db_index=True)

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_measurement_log"
        ordering = ("-recorded_at",)
