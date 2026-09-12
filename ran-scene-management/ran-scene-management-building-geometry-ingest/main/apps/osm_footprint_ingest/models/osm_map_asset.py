"""osm_map_asset — 一張 OSM bbox 產生的地圖與產物路徑(一個 table 一個檔案)。"""
from django.db import models


class OsmMapAsset(models.Model):
    id = models.AutoField(primary_key=True)
    osm_map_asset_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=128, unique=True, db_index=True)
    label = models.CharField(max_length=256, blank=True, default="")
    min_lon = models.FloatField()
    min_lat = models.FloatField()
    max_lon = models.FloatField()
    max_lat = models.FloatField()
    origin_lat = models.FloatField(null=True, blank=True)
    origin_lon = models.FloatField(null=True, blank=True)
    mitsuba_xml = models.CharField(max_length=512, blank=True, default="")
    footprints_json = models.CharField(max_length=512, blank=True, default="")
    building_count = models.IntegerField(default=0)
    height_max_m = models.FloatField(default=0.0)
    extent_ew_m = models.FloatField(default=0.0)
    extent_ns_m = models.FloatField(default=0.0)
    status = models.CharField(max_length=16, default="pending", db_index=True)
    error = models.TextField(blank=True, default="")
    osm_map_asset_created_at = models.DateTimeField()
    osm_map_asset_updated_at = models.DateTimeField()

    class Meta:
        app_label = "osm_footprint_ingest"
        db_table = "osm_footprint_ingest_osm_map_asset"
        ordering = ("id",)
