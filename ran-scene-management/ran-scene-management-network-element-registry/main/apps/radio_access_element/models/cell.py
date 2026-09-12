"""cell — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class Cell(models.Model):
    id = models.AutoField(primary_key=True)
    cell_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    du = models.ForeignKey("radio_access_element.Du", on_delete=models.CASCADE, to_field="du_uuid", db_column="f_du_uuid", related_name="cells", db_index=True)
    name = models.CharField(max_length=128)
    pci = models.IntegerField(default=0)
    nr_cellid = models.BigIntegerField(null=True, blank=True)
    arfcn = models.IntegerField(null=True, blank=True)
    band = models.CharField(max_length=16, default='n78')
    bandwidth_mhz = models.FloatField(default=40.0)
    position = models.JSONField(null=True, blank=True)
    azimuth_deg = models.FloatField(default=0.0)
    tilt_deg = models.FloatField(default=0.0)
    power_dbm = models.FloatField(default=23.0)
    is_active = models.BooleanField(default=True)
    is_barred = models.BooleanField(default=False)
    cell_created_at = models.DateTimeField()
    cell_updated_at = models.DateTimeField()

    class Meta:
        app_label = "radio_access_element"
        db_table = "radio_access_element_cell"
        ordering = ("id",)
