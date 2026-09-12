"""ue_active_window — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class UeActiveWindow(models.Model):
    id = models.AutoField(primary_key=True)
    ue_active_window_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    ue = models.ForeignKey("user_equipment.Ue", on_delete=models.CASCADE, to_field="ue_uuid", db_column="f_ue_uuid", related_name="active_windows", db_index=True)
    t0_sec = models.FloatField(default=0.0)
    t1_sec = models.FloatField(default=0.0)
    ue_active_window_created_at = models.DateTimeField()
    ue_active_window_updated_at = models.DateTimeField()

    class Meta:
        app_label = "user_equipment"
        db_table = "user_equipment_ue_active_window"
        ordering = ("id",)
