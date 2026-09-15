"""run_knob — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class RunKnob(models.Model):
    id = models.AutoField(primary_key=True)
    run_knob_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    scene_run = models.ForeignKey("simulation_run.SceneRun", on_delete=models.CASCADE, to_field="scene_run_uuid", db_column="f_scene_run_uuid", related_name="knobs", db_index=True)
    key = models.CharField(max_length=64)
    value = models.JSONField(null=True, blank=True)
    run_knob_created_at = models.DateTimeField()
    run_knob_updated_at = models.DateTimeField()

    class Meta:
        app_label = "simulation_run"
        db_table = "simulation_run_run_knob"
        ordering = ("id",)
