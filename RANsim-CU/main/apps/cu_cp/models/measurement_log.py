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
    # 累計 bytes per measurement window — 對齊 3GPP TS 28.552 DRB.PdcpSduVolumeDL/UL
    pdcp_sdu_volume_dl = models.BigIntegerField(default=0)
    pdcp_sdu_volume_ul = models.BigIntegerField(default=0)
    rlc_sdu_delay_dl_ms = models.FloatField(default=0.0)
    # 2026-08-12(D):UE 的 5QI → delay/thp per-5QI 分桶(AirIfDelayDlAvg.5QI1 轉真)
    qos_5qi = models.IntegerField(default=9)
    neighbor_cells_json = models.JSONField(default=list)
    # 2026-08-26 第三十輪:量測「當時」的 serving cell。bySourceCell 歸屬曾用
    # 查詢當下的 UeContext.serving_cell,UE 移動時整窗樣本被記到單一 cell(argmax 假象)。
    serving_cell = models.CharField(max_length=64, default="", blank=True)

    recorded_at = models.DateTimeField(db_index=True)

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_measurement_log"
        ordering = ("-recorded_at",)
