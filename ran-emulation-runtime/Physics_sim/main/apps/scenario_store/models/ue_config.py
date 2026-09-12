"""UeConfig — 鏡像 Omniverse ran.UeConfig(欄位一致,回應形狀相同)。"""
from django.db import models


class UeConfig(models.Model):
    id = models.AutoField(primary_key=True)
    ue_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=128, unique=True, db_index=True)
    waypoints_json = models.JSONField(default=list)
    speed_mps = models.FloatField(default=1.0)
    loop = models.BooleanField(default=True)
    pos_x = models.FloatField(default=0)
    pos_y = models.FloatField(default=0)
    pos_z = models.FloatField(default=0)
    color_r = models.FloatField(default=0.5)
    color_g = models.FloatField(default=0.5)
    color_b = models.FloatField(default=0.5)
    usd_path = models.CharField(max_length=512, blank=True, default="")
    preset_type = models.CharField(max_length=128, blank=True, default="")
    target_height_m = models.FloatField(null=True, blank=True)
    ue_created_at = models.DateTimeField(auto_now_add=True)
    ue_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "scenario_store"
        db_table = "ue_config"
