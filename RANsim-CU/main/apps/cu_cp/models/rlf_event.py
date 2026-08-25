"""RlfEvent — 無線鏈路失敗事件審計(P1-1,2026-08-12)。

DU 偵測 RLF → 通報 CU → 落此表。CU 據此驅動 UE 重建(P1-2)並更新結果:
  outcome: DECLARED → REESTAB_WITH_CTX / REESTAB_WITHOUT_CTX / DROP
對應 ANR 卷:RLF.DetectedRate、RLF.DropWithoutReestablishmentRate、
reestablishmentInboundByPreviousPci(previous_pci)。
"""
from __future__ import annotations

from django.db import models


class RlfEvent(models.Model):
    OUTCOME_CHOICES = (
        ("DECLARED", "DECLARED"),
        ("REESTAB_WITH_CTX", "REESTAB_WITH_CTX"),
        ("REESTAB_WITHOUT_CTX", "REESTAB_WITHOUT_CTX"),
        ("DROP", "DROP"),
    )

    id = models.AutoField(primary_key=True)
    ue_id = models.CharField(max_length=64, db_index=True)

    source_cell = models.CharField(max_length=64, db_index=True)  # RLF 發生時的 serving cell
    source_pci = models.IntegerField(default=-1)                  # → previousPci
    sinr_at_rlf = models.FloatField(default=0.0)
    t310_ms = models.FloatField(default=0.0)
    reason = models.CharField(max_length=32, default="T310_EXPIRY")

    # 重建落點(P1-2 填)
    reestab_cell = models.CharField(max_length=64, blank=True, default="")
    reestab_pci = models.IntegerField(default=-1)
    outcome = models.CharField(max_length=24, choices=OUTCOME_CHOICES, default="DECLARED")

    detected_at = models.DateTimeField(db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_rlf_event"
        ordering = ("-detected_at",)
