"""RLC entity 元數據 — 一個 UE 的一條 SRB/DRB 一筆。"""
from django.db import models


class RlcEntity(models.Model):
    MODE_CHOICES = [("AM", "AM"), ("UM", "UM"), ("TM", "TM")]
    BEARER_CHOICES = [("SRB", "SRB"), ("DRB", "DRB")]

    id = models.AutoField(primary_key=True)
    rlc_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    ue_id = models.CharField(max_length=64, db_index=True)
    bearer_type = models.CharField(max_length=4, choices=BEARER_CHOICES)
    bearer_id = models.IntegerField()  # SRB id 0..3 / DRB id 1..32
    mode = models.CharField(max_length=4, choices=MODE_CHOICES)
    sn_field_length = models.IntegerField(default=12)
    tx_buffer_bytes = models.IntegerField(default=0)
    rx_buffer_bytes = models.IntegerField(default=0)
    retx_count = models.IntegerField(default=0)
    status_pdu_pending = models.BooleanField(default=False)
    rlc_created_at = models.BigIntegerField()
    rlc_updated_at = models.BigIntegerField()

    class Meta:
        app_label = "rlc"
        db_table = "rlc_entity"
        unique_together = (("ue_id", "bearer_type", "bearer_id"),)
