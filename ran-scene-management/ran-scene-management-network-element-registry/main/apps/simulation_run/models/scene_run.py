"""scene_run — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class SceneRun(models.Model):
    id = models.AutoField(primary_key=True)
    scene_run_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    scene = models.ForeignKey("scene_layout.Scene", on_delete=models.CASCADE, to_field="scene_uuid", db_column="f_scene_uuid", related_name="runs", db_index=True)
    mode = models.CharField(max_length=8, default='cached')
    speed_x = models.FloatField(default=1.0)
    sim_dt_ms = models.IntegerField(default=500)
    duration_sec = models.IntegerField(default=60)
    status = models.CharField(max_length=16, default='pending')
    cache_path = models.CharField(max_length=512, blank=True, default='')
    gnb_id_hex = models.CharField(max_length=16, blank=True, default='')   # per-run CU 的 GNB_ID_HEX(22-bit),RIC meid 由此推導
    e2_node_id = models.CharField(max_length=64, blank=True, default='')
    snapshot_json = models.JSONField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    scene_run_created_at = models.DateTimeField()
    scene_run_updated_at = models.DateTimeField()

    class Meta:
        app_label = "simulation_run"
        db_table = "simulation_run_scene_run"
        ordering = ("id",)
