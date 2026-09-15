"""du — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class Du(models.Model):
    id = models.AutoField(primary_key=True)
    du_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    gnb = models.ForeignKey("equipment_ran.Gnb", on_delete=models.CASCADE, to_field="gnb_uuid", db_column="f_gnb_uuid", related_name="dus", db_index=True)
    name = models.CharField(max_length=128)
    gnb_du_id = models.IntegerField(default=1)
    config_template = models.ForeignKey("equipment_preset.DuConfigTemplate", on_delete=models.PROTECT, to_field="du_config_template_uuid", db_column="f_du_config_template_uuid", related_name="dus", db_index=True, null=True, blank=True)
    config_override = models.JSONField(null=True, blank=True)
    du_created_at = models.DateTimeField()
    du_updated_at = models.DateTimeField()

    class Meta:
        app_label = "equipment_ran"
        db_table = "radio_access_element_du"
        ordering = ("id",)
