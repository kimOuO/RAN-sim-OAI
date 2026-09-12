"""antenna_preset — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class AntennaPreset(models.Model):
    id = models.AutoField(primary_key=True)
    antenna_preset_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=128, unique=True)
    source = models.CharField(max_length=16, default='3gpp')
    pattern = models.CharField(max_length=16, default='tr38901')
    rows = models.IntegerField(default=1)
    cols = models.IntegerField(default=1)
    polarization = models.CharField(max_length=8, default='V')
    v_spacing = models.FloatField(default=0.5)
    h_spacing = models.FloatField(default=0.5)
    polarization_model = models.CharField(max_length=16, default='tr38901_2')
    max_gain_dbi = models.FloatField(default=8.0)
    notes = models.TextField(blank=True, default='')
    antenna_preset_created_at = models.DateTimeField()
    antenna_preset_updated_at = models.DateTimeField()

    class Meta:
        app_label = "preset_catalog"
        db_table = "preset_catalog_antenna_preset"
        ordering = ("id",)
