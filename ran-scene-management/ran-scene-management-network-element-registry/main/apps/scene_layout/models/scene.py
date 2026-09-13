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
    # 劇本匯入相容:原 scenario_id(往返用)、原 scene_id(Physics/Omniverse 幾何場景預設名)、geometry_source(倉庫版劇本)
    legacy_scenario_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    geometry_scene_id = models.CharField(max_length=128, blank=True, default="")
    geometry_source = models.JSONField(null=True, blank=True)
    ground_material = models.ForeignKey("preset_catalog.Material", on_delete=models.PROTECT, to_field="material_uuid", db_column="f_material_uuid", related_name="scenes", db_index=True, null=True, blank=True)
    # run 層級天線(Sionna 的 tx_array / rx_array 是 scene-global,一個 run 只能一組;P5-Q2 2026-09-13)
    # None → gNB 取第一個 cell 的 RU preset、UE 取第一個 UE 的 preset(舊行為),都沒有就 1×1。
    gnb_antenna_preset = models.ForeignKey("preset_catalog.AntennaPreset", on_delete=models.SET_NULL, to_field="antenna_preset_uuid", db_column="f_gnb_antenna_preset_uuid", related_name="scenes_as_gnb", null=True, blank=True)
    ue_antenna_preset = models.ForeignKey("preset_catalog.AntennaPreset", on_delete=models.SET_NULL, to_field="antenna_preset_uuid", db_column="f_ue_antenna_preset_uuid", related_name="scenes_as_ue", null=True, blank=True)
    scene_created_at = models.DateTimeField()
    scene_updated_at = models.DateTimeField()

    class Meta:
        app_label = "scene_layout"
        db_table = "scene_layout_scene"
        ordering = ("id",)
