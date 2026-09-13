"""gnb_config_template — 一個 table 一個檔案(backend_rule §5-1)。
gNB 級參數組(PLMN、A3、cell 預設 RF、綁定 DU 模板與天線 preset)。場景裡的 gNB 可「套用」它(快速填值,現場仍可改),也可把現場 gNB 「存成 / 更新」成一個模板。
預設一組「OAI 對齊」(值來自 DU/CU 目前對齊 OAI rfsim band78 106 PRB 的設定),由 seed_presets 建立。"""
from django.db import models


class GnbConfigTemplate(models.Model):
    id = models.AutoField(primary_key=True)
    gnb_config_template_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=128, unique=True)
    source = models.CharField(max_length=16, default='custom')   # oai | custom
    notes = models.TextField(blank=True, default='')
    plmn_mcc = models.CharField(max_length=3, default='208')
    plmn_mnc = models.CharField(max_length=3, default='95')
    a3_enabled = models.BooleanField(default=False)
    a3_offset_db = models.FloatField(default=1.0)
    a3_hys_db = models.FloatField(default=0.5)
    a3_ttt_ms = models.IntegerField(default=80)
    band = models.CharField(max_length=16, default='n78')
    center_frequency_ghz = models.FloatField(default=3.5)
    bandwidth_mhz = models.FloatField(default=40.0)
    power_dbm = models.FloatField(default=23.0)
    tilt_deg = models.FloatField(default=0.0)
    cells_per_gnb = models.IntegerField(default=1)
    azimuth_step_deg = models.FloatField(default=120.0)
    du_config_template = models.ForeignKey("preset_catalog.DuConfigTemplate", on_delete=models.PROTECT, to_field="du_config_template_uuid", db_column="f_du_config_template_uuid", related_name="gnb_templates", null=True, blank=True)
    antenna_preset = models.ForeignKey("preset_catalog.AntennaPreset", on_delete=models.PROTECT, to_field="antenna_preset_uuid", db_column="f_antenna_preset_uuid", related_name="gnb_templates", null=True, blank=True)
    gnb_config_template_created_at = models.DateTimeField()
    gnb_config_template_updated_at = models.DateTimeField()

    class Meta:
        app_label = "preset_catalog"
        db_table = "preset_catalog_gnb_config_template"
        ordering = ("id",)
