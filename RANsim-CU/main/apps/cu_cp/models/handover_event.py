"""HandoverEvent — every A3-triggered or manual HO is logged here."""
from __future__ import annotations

from django.db import models


class HandoverEvent(models.Model):
    STATUS_CHOICES = (
        ("PREP", "PREP"),
        ("EXEC", "EXEC"),
        ("SUCC", "SUCC"),
        ("FAIL", "FAIL"),
    )
    TRIGGER_CHOICES = (
        ("A3_TTT", "A3_TTT"),
        ("MANUAL", "MANUAL"),
    )

    id = models.AutoField(primary_key=True)
    ho_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    ue_id = models.CharField(max_length=64, db_index=True)
    source_cell = models.CharField(max_length=64)
    target_cell = models.CharField(max_length=64)
    trigger = models.CharField(max_length=16, choices=TRIGGER_CHOICES, default="A3_TTT")
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="PREP")

    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_handover_event"
        ordering = ("-started_at",)
