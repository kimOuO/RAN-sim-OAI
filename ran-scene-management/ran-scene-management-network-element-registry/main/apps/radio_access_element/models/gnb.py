"""gnb — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class Gnb(models.Model):
    id = models.AutoField(primary_key=True)
    gnb_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    scene = models.ForeignKey("scene_layout.Scene", on_delete=models.CASCADE, to_field="scene_uuid", db_column="f_scene_uuid", related_name="gnbs", db_index=True)
    name = models.CharField(max_length=128)
    gnb_id = models.IntegerField(default=0)
    plmn_mcc = models.CharField(max_length=3, default='208')
    plmn_mnc = models.CharField(max_length=3, default='95')
    position = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)   # 劇本 gnbs[].active(ES 節能)
    color = models.JSONField(null=True, blank=True)
    a3_enabled = models.BooleanField(null=True, blank=True)   # None = 劇本未指定 → CU env 預設
    a3_offset_db = models.FloatField(null=True, blank=True)
    a3_hys_db = models.FloatField(null=True, blank=True)
    a3_ttt_ms = models.IntegerField(null=True, blank=True)
    gnb_created_at = models.DateTimeField()
    gnb_updated_at = models.DateTimeField()

    class Meta:
        app_label = "radio_access_element"
        db_table = "radio_access_element_gnb"
        ordering = ("id",)
