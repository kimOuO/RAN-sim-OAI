"""run_handover_event — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §10.4。"""
from django.db import models


class RunHandoverEvent(models.Model):
    id = models.AutoField(primary_key=True)
    run_handover_event_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    # 第幾次執行(同一個 scene_run 每次 start +1,對齊 RIC 閘道的 `run` 場次號)。
    # 2026-09-19:沒有這個欄位時,同一 run uuid 多次執行的資料混在一起,查詢極易誤判。
    run_seq = models.IntegerField(default=0, db_index=True)
    # RIC 閘道宣告回應裡的 `run` 場次號(他們每次宣告 +1,含白跑的)。與我們的 run_seq 是兩套計數,
    # 記下來兩邊對資料才不用換算;RIC InfluxDB 的 `run` 標籤就是這個值。0 = 未知/未宣告。
    ric_run = models.IntegerField(default=0, db_index=True)
    f_scene_run_uuid = models.CharField(max_length=255, db_index=True, help_text='Reference to registry scene_run.scene_run_uuid')
    at_sim_ms = models.BigIntegerField(default=0)
    ue_id = models.CharField(max_length=128)
    source_cell = models.CharField(max_length=128)
    target_cell = models.CharField(max_length=128)
    outcome = models.CharField(max_length=16, default='success')
    detail = models.JSONField(null=True, blank=True)
    run_handover_event_created_at = models.DateTimeField()
    run_handover_event_updated_at = models.DateTimeField()

    class Meta:
        app_label = "run_telemetry_archive"
        db_table = "run_telemetry_archive_run_handover_event"
        ordering = ("id",)
