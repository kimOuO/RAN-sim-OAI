"""MeasurementLog — sliding-window record of GnbDuMeasurementReport.

Used by E2KPM aggregator and by A3 algorithm (last-state lookup).
"""
from __future__ import annotations

from django.db import models


class MeasurementLog(models.Model):
    id = models.AutoField(primary_key=True)
    meas_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    ue_id = models.CharField(max_length=64, db_index=True)
    # null = 該視窗無量測樣本(不是量到 0)
    rsrp_dbm = models.FloatField(null=True, blank=True)
    sinr_db = models.FloatField(null=True, blank=True)
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
    # P6 / P5-4(2026-09-14):上行 MCS / PRB / SINR@gNB、每層 SINR
    mcs_ul = models.IntegerField(default=0)
    rb_width_ul = models.IntegerField(default=0)
    ul_sinr_db = models.FloatField(null=True, blank=True)
    sinr_layers_json = models.JSONField(default=list)
    # B1(2026-09-16):O-RAN Cat B 的 GoB 波束 id
    beam_id = models.IntegerField(null=True, blank=True)
    # DU 的 PM 視窗序號:歸檔照它分組,避免同一秒內兩份報告互相覆蓋(實測丟 47%)
    window_seq = models.IntegerField(null=True, blank=True, db_index=True)
    # 2026-09-19:每波束 RSRP [[beam_id, 相對最佳波束 dB], …](O-RAN WG1 §4.6.4.1);空 = 沒有 GoB
    beam_rsrp_top_json = models.JSONField(default=list, blank=True)
    # 2026-08-26 第三十輪:量測「當時」的 serving cell。bySourceCell 歸屬曾用
    # 查詢當下的 UeContext.serving_cell,UE 移動時整窗樣本被記到單一 cell(argmax 假象)。
    serving_cell = models.CharField(max_length=64, default="", blank=True)

    # 2026-09-22:服務 cell 的 RSRQ(TS 38.215)。以前完全沒有這個欄位,
    # 鄰區的則固定填 0.0(宣告了卻沒算)。null = 算不出來。
    rsrq_db = models.FloatField(null=True, blank=True)
    # 寬頻 CQI(0~15 的加權平均,故用浮點)。null = 舊版 DU 沒帶。
    cqi = models.FloatField(null=True, blank=True)
    # 2026-09-22:劇本時鐘(DU 的 scene_tick × sim_dt_ms)。null = 舊版 DU 沒帶,
    # 歸檔退回原本的 tick 累加推算。
    scene_sim_ms = models.BigIntegerField(null=True, blank=True)
    recorded_at = models.DateTimeField(db_index=True)

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_measurement_log"
        ordering = ("-recorded_at",)
