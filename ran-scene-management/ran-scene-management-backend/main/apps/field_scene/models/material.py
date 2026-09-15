"""material — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class Material(models.Model):
    id = models.AutoField(primary_key=True)
    material_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    key = models.CharField(max_length=32, unique=True)
    itu_id = models.CharField(max_length=64)
    freq_range_ghz = models.CharField(max_length=32, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    material_created_at = models.DateTimeField()
    material_updated_at = models.DateTimeField()

    class Meta:
        app_label = "field_scene"
        db_table = "preset_catalog_material"
        ordering = ("id",)
