"""run_handover_event — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §10.4。"""
from django.db import models


class RunHandoverEvent(models.Model):
    id = models.AutoField(primary_key=True)
    run_handover_event_uuid = models.CharField(max_length=255, unique=True, db_index=True)
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
