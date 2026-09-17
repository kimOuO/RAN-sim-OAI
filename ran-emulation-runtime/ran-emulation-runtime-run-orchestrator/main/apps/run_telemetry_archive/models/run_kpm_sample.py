"""run_kpm_sample — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §10.4。"""
from django.db import models


class RunKpmSample(models.Model):
    id = models.AutoField(primary_key=True)
    run_kpm_sample_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    f_scene_run_uuid = models.CharField(max_length=255, db_index=True, help_text='Reference to registry scene_run.scene_run_uuid')
    window_index = models.IntegerField(default=0)
    sim_time_ms = models.BigIntegerField(default=0)
    wall_time_ms = models.BigIntegerField(default=0)
    per_cell = models.JSONField(default=dict)
    per_ue = models.JSONField(default=dict)
    warnings = models.JSONField(default=list)
    # 2026-09-17:這個視窗對應的劇本時間(秒,UE driver 的 elapsed_sim_sec)。3D 回放用它算 UE 位置;
    # sim_time_ms 是跨重啟累加的,不能直接對劇本路徑。舊資料 = null。
    scene_t_sec = models.FloatField(null=True, blank=True)
    run_kpm_sample_created_at = models.DateTimeField()
    run_kpm_sample_updated_at = models.DateTimeField()

    class Meta:
        app_label = "run_telemetry_archive"
        db_table = "run_telemetry_archive_run_kpm_sample"
        ordering = ("id",)
