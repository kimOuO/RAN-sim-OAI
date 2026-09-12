"""ru — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class Ru(models.Model):
    id = models.AutoField(primary_key=True)
    ru_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    cell = models.OneToOneField("radio_access_element.Cell", on_delete=models.CASCADE, to_field="cell_uuid", db_column="f_cell_uuid", related_name="ru", db_index=True)
    name = models.CharField(max_length=128)
    antenna_preset = models.ForeignKey("preset_catalog.AntennaPreset", on_delete=models.PROTECT, to_field="antenna_preset_uuid", db_column="f_antenna_preset_uuid", related_name="rus", db_index=True, null=True, blank=True)
    antenna_override = models.JSONField(null=True, blank=True)
    noise_figure_db = models.FloatField(default=5.0)
    ru_created_at = models.DateTimeField()
    ru_updated_at = models.DateTimeField()

    class Meta:
        app_label = "radio_access_element"
        db_table = "radio_access_element_ru"
        ordering = ("id",)
