"""F1 session — DU 與 CU 之間的 SCTP-equivalent 連線狀態(這裡是 HTTP)。"""
from django.db import models


class F1Session(models.Model):
    STATE_CHOICES = [
        ("INIT", "INIT"),
        ("SETUP_SENT", "SETUP_SENT"),
        ("ACTIVE", "ACTIVE"),
        ("FAILED", "FAILED"),
    ]

    id = models.AutoField(primary_key=True)
    f1_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    gnb_du_id = models.IntegerField()
    cu_host = models.CharField(max_length=128)
    cu_port = models.IntegerField()
    transaction_id = models.IntegerField(default=0)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default="INIT")
    last_setup_at = models.BigIntegerField(null=True)
    f1_session_updated_at = models.BigIntegerField()

    class Meta:
        app_label = "f1ap_du"
        db_table = "f1_session"
