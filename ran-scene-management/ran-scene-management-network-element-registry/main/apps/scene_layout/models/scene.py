"""scene — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class Scene(models.Model):
    id = models.AutoField(primary_key=True)
    scene_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default='')
    origin_lat = models.FloatField(null=True, blank=True)
    origin_lon = models.FloatField(null=True, blank=True)
    bounds = models.JSONField(null=True, blank=True)
    ground_material = models.ForeignKey("preset_catalog.Material", on_delete=models.PROTECT, to_field="material_uuid", db_column="f_material_uuid", related_name="scenes", db_index=True, null=True, blank=True)
    scene_created_at = models.DateTimeField()
    scene_updated_at = models.DateTimeField()

    class Meta:
        app_label = "scene_layout"
        db_table = "scene_layout_scene"
        ordering = ("id",)
