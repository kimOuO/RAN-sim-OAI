"""run_control_event — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §10.4。"""
from django.db import models


class RunControlEvent(models.Model):
    id = models.AutoField(primary_key=True)
    run_control_event_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    f_scene_run_uuid = models.CharField(max_length=255, db_index=True, help_text='Reference to registry scene_run.scene_run_uuid')
    at_sim_ms = models.BigIntegerField(default=0)
    source = models.CharField(max_length=64, blank=True, default='')
    action_type = models.CharField(max_length=32)
    target = models.CharField(max_length=128, blank=True, default='')
    outcome = models.CharField(max_length=16, default='pending')
    landing_latency_ms = models.IntegerField(null=True, blank=True)
    detail = models.JSONField(null=True, blank=True)
    run_control_event_created_at = models.DateTimeField()
    run_control_event_updated_at = models.DateTimeField()

    class Meta:
        app_label = "run_telemetry_archive"
        db_table = "run_telemetry_archive_run_control_event"
        ordering = ("id",)
