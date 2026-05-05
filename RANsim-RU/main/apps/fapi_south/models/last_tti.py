"""LastTti — 偵錯/Dashboard 用的最近一筆 TTI 結果（per UE）。

非必經；rolling latest by ue_id。
"""
from django.db import models


class LastTti(models.Model):
    id = models.AutoField(primary_key=True)
    last_tti_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    direction = models.CharField(max_length=4)   # "DL" | "UL"
    ue_id = models.CharField(max_length=128, db_index=True)
    sfn = models.IntegerField()
    slot = models.IntegerField()

    sinr_db = models.FloatField()
    cqi = models.IntegerField(default=0)
    rank = models.IntegerField(default=1)
    pmi = models.IntegerField(default=0)
    harq_pid = models.IntegerField(default=0)
    success = models.BooleanField(default=True)

    last_tti_created_at = models.DateTimeField()
    last_tti_updated_at = models.DateTimeField()

    class Meta:
        db_table = "ru_last_tti"
        unique_together = (("ue_id", "direction"),)
        ordering = ["-last_tti_updated_at"]
