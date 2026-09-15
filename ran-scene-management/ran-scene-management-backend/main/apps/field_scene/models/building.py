"""building — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class Building(models.Model):
    id = models.AutoField(primary_key=True)
    building_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    scene = models.ForeignKey("field_scene.Scene", on_delete=models.CASCADE, to_field="scene_uuid", db_column="f_scene_uuid", related_name="buildings", db_index=True)
    name = models.CharField(max_length=128)
    source = models.CharField(max_length=16, default='manual_box')
    geometry_ref = models.CharField(max_length=512, blank=True, default='')
    position = models.JSONField(default=list)
    rotation = models.JSONField(default=list)
    scale = models.JSONField(default=list)
    size = models.JSONField(default=list)
    default_material = models.ForeignKey("field_scene.Material", on_delete=models.PROTECT, to_field="material_uuid", db_column="f_material_uuid", related_name="buildings", db_index=True, null=True, blank=True)
    materials_npz = models.CharField(max_length=512, blank=True, default='')
    building_created_at = models.DateTimeField()
    building_updated_at = models.DateTimeField()

    class Meta:
        app_label = "field_scene"
        db_table = "scene_layout_building"
        ordering = ("id",)
