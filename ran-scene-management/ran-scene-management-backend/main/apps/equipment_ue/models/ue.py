"""ue — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class Ue(models.Model):
    id = models.AutoField(primary_key=True)
    ue_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    scene = models.ForeignKey("field_scene.Scene", on_delete=models.CASCADE, to_field="scene_uuid", db_column="f_scene_uuid", related_name="ues", db_index=True)
    name = models.CharField(max_length=128)
    antenna_preset = models.ForeignKey("equipment_preset.AntennaPreset", on_delete=models.PROTECT, to_field="antenna_preset_uuid", db_column="f_antenna_preset_uuid", related_name="ues", db_index=True, null=True, blank=True)
    antenna_height_m = models.FloatField(default=1.5)
    qos_5qi = models.IntegerField(default=9)
    color = models.JSONField(default=list)
    loop = models.BooleanField(default=False)          # 倉庫版劇本:軌跡循環
    speed_mps = models.FloatField(null=True, blank=True)
    ue_created_at = models.DateTimeField()
    ue_updated_at = models.DateTimeField()

    class Meta:
        app_label = "equipment_ue"
        db_table = "user_equipment_ue"
        ordering = ("id",)
