"""scan_asset — 一份掃描 GLB 的匯入紀錄與產物路徑(一個 table 一個檔案)。"""
from django.db import models


class ScanAsset(models.Model):
    id = models.AutoField(primary_key=True)
    scan_asset_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=128, unique=True, db_index=True)
    label = models.CharField(max_length=256, blank=True, default="")
    glb_path = models.CharField(max_length=512, blank=True, default="")
    materials_npz = models.CharField(max_length=512, blank=True, default="")
    materials_json = models.CharField(max_length=512, blank=True, default="")
    mitsuba_xml = models.CharField(max_length=512, blank=True, default="")
    import_stats = models.JSONField(null=True, blank=True)
    radio_materials = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=16, default="pending", db_index=True)
    error = models.TextField(blank=True, default="")
    scan_asset_created_at = models.DateTimeField()
    scan_asset_updated_at = models.DateTimeField()

    class Meta:
        app_label = "render_scan_mesh"
        db_table = "scan_mesh_ingest_scan_asset"
        ordering = ("id",)
