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
    run_kpm_sample_created_at = models.DateTimeField()
    run_kpm_sample_updated_at = models.DateTimeField()

    class Meta:
        app_label = "run_telemetry_archive"
        db_table = "run_telemetry_archive_run_kpm_sample"
        ordering = ("id",)
