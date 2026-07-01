"""GnbConfig — 鏡像 Omniverse ran.GnbConfig(欄位一致,回應形狀相同)。"""
from django.db import models


class GnbConfig(models.Model):
    id = models.AutoField(primary_key=True)
    gnb_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=128, unique=True, db_index=True)
    freq_mhz = models.FloatField()
    power_dbm = models.FloatField()
    bw_hz = models.FloatField()
    active = models.BooleanField(default=True)
    pos_x = models.FloatField(default=0)
    pos_y = models.FloatField(default=0)
    pos_z = models.FloatField(default=0)
    color_r = models.FloatField(default=1.0)
    color_g = models.FloatField(default=1.0)
    color_b = models.FloatField(default=1.0)
    target_height_m = models.FloatField(null=True, blank=True)
    cells = models.JSONField(null=True, blank=True, default=list)
    gnb_created_at = models.DateTimeField(auto_now_add=True)
    gnb_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "scenario_store"
        db_table = "gnb_config"
