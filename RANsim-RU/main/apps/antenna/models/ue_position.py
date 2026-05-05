"""UePosition — 每個 UE 的當前位置（被 update_ues 覆寫；fapi_south 讀來打 Physics）。"""
from django.db import models


class UePosition(models.Model):
    id = models.AutoField(primary_key=True)
    ue_position_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    ue_id = models.CharField(max_length=128, unique=True, db_index=True)

    position_x = models.FloatField()
    position_y = models.FloatField()
    position_z = models.FloatField()

    velocity_x = models.FloatField(default=0.0)
    velocity_y = models.FloatField(default=0.0)
    velocity_z = models.FloatField(default=0.0)

    ue_position_created_at = models.DateTimeField()
    ue_position_updated_at = models.DateTimeField()

    class Meta:
        db_table = "ru_ue_position"
        ordering = ["ue_id"]
