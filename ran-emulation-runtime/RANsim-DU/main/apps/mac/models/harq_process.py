"""HARQ process — 每 UE 16 個 DL + 16 個 UL。對應 OAI 的 NR_UE_harq_t。"""
from django.db import models


class HarqProcess(models.Model):
    DIRECTION_CHOICES = [("DL", "DL"), ("UL", "UL")]
    STATE_CHOICES = [
        ("NEW", "NEW"),
        ("WAIT_FEEDBACK", "WAIT_FEEDBACK"),
        ("RETX", "RETX"),
        ("DONE", "DONE"),
    ]

    id = models.AutoField(primary_key=True)
    harq_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    f_ue_mac_uuid = models.CharField(max_length=255, db_index=True)
    harq_pid = models.IntegerField()  # 0..15
    direction = models.CharField(max_length=4, choices=DIRECTION_CHOICES)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default="NEW")
    retx_count = models.IntegerField(default=0)
    last_tbs_bytes = models.IntegerField(default=0)
    harq_updated_at = models.BigIntegerField()

    class Meta:
        app_label = "mac"
        db_table = "mac_harq_process"
        unique_together = (("f_ue_mac_uuid", "harq_pid", "direction"),)
