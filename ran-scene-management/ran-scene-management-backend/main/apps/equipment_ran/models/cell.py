"""cell — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class Cell(models.Model):
    id = models.AutoField(primary_key=True)
    cell_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    du = models.ForeignKey("equipment_ran.Du", on_delete=models.CASCADE, to_field="du_uuid", db_column="f_du_uuid", related_name="cells", db_index=True)
    name = models.CharField(max_length=128)
    pci = models.IntegerField(default=0)
    nr_cellid = models.BigIntegerField(null=True, blank=True)   # 舊欄位,執行期不用;NCI 由 gNB ID ‖ local_cell_id 推導
    # 2026-09-27 多 gNB:gNB 內的本地 cell ID(0–16383),NCI = gNB ID(22 bit)‖ local_cell_id(14 bit)。
    # 建立時配該 gNB 內最小空號,之後不變,cell 的 NCI / NCGI 才穩定(ran_sim_protocol.e2_identity)。
    local_cell_id = models.IntegerField(null=True, blank=True)
    arfcn = models.IntegerField(null=True, blank=True)
    # 精確中心頻率(GHz)。ARFCN 是 38.104 raster 上的量化值(5/15 kHz),劇本常給非 raster 值(如 3.5 GHz),
    # 保留原值才能無損往返;arfcn 由此推導。
    center_frequency_ghz = models.FloatField(null=True, blank=True)
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
        app_label = "equipment_ran"
        db_table = "radio_access_element_cell"
        ordering = ("id",)
