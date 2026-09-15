"""ue_traffic — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class UeTraffic(models.Model):
    id = models.AutoField(primary_key=True)
    ue_traffic_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    ue = models.ForeignKey("equipment_ue.Ue", on_delete=models.CASCADE, to_field="ue_uuid", db_column="f_ue_uuid", related_name="traffics", db_index=True)
    pattern = models.CharField(max_length=16, default='cbr')
    rate_mbps = models.FloatField(default=0.0)
    schedule = models.JSONField(null=True, blank=True)
    bearer_id = models.IntegerField(default=1)
    ue_traffic_created_at = models.DateTimeField()
    ue_traffic_updated_at = models.DateTimeField()

    class Meta:
        app_label = "equipment_ue"
        db_table = "user_equipment_ue_traffic"
        ordering = ("id",)
