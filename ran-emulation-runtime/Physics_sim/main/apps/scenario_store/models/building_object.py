"""BuildingObject — 鏡像 Omniverse ran.BuildingObject(欄位一致,回應形狀相同)。"""
from django.db import models


class BuildingObject(models.Model):
    id = models.AutoField(primary_key=True)
    building_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=128, unique=True, db_index=True)
    scene_id = models.CharField(max_length=128, blank=True, default="")
    pos_x = models.FloatField(default=0)
    pos_y = models.FloatField(default=0)
    pos_z = models.FloatField(default=0)
    size_x = models.FloatField(default=10)
    size_y = models.FloatField(default=10)
    size_z = models.FloatField(default=10)
    color_r = models.FloatField(default=0.75)
    color_g = models.FloatField(default=0.75)
    color_b = models.FloatField(default=0.75)
    usd_path = models.CharField(max_length=512, blank=True, default="")
    preset_type = models.CharField(max_length=128, blank=True, default="")
    target_height_m = models.FloatField(null=True, blank=True)
    rot_x = models.FloatField(default=0)
    rot_y = models.FloatField(default=0)
    rot_z = models.FloatField(default=0)
    material = models.CharField(max_length=128, blank=True, default="")
    building_created_at = models.DateTimeField(auto_now_add=True)
    building_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "scenario_store"
        db_table = "building_object"
