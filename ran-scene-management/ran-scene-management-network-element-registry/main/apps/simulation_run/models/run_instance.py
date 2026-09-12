"""run_instance — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class RunInstance(models.Model):
    id = models.AutoField(primary_key=True)
    run_instance_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    scene_run = models.ForeignKey("simulation_run.SceneRun", on_delete=models.CASCADE, to_field="scene_run_uuid", db_column="f_scene_run_uuid", related_name="instances", db_index=True)
    role = models.CharField(max_length=16)
    container_id = models.CharField(max_length=128, blank=True, default='')
    host_port = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, default='pending')
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    run_instance_created_at = models.DateTimeField()
    run_instance_updated_at = models.DateTimeField()

    class Meta:
        app_label = "simulation_run"
        db_table = "simulation_run_run_instance"
        ordering = ("id",)
