"""launch_request — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §10.4。"""
from django.db import models


class LaunchRequest(models.Model):
    id = models.AutoField(primary_key=True)
    launch_request_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    f_scene_run_uuid = models.CharField(max_length=255, db_index=True, help_text='Reference to registry scene_run.scene_run_uuid')
    action = models.CharField(max_length=16)
    mode = models.CharField(max_length=8, default='cached')
    speed_x = models.FloatField(default=1.0)
    status = models.CharField(max_length=16, default='accepted')
    detail = models.JSONField(null=True, blank=True)
    launch_request_created_at = models.DateTimeField()
    launch_request_updated_at = models.DateTimeField()

    class Meta:
        app_label = "run_lifecycle"
        db_table = "run_lifecycle_launch_request"
        ordering = ("id",)
