"""Drb — Data Radio Bearer instance on CU-UP.

OAI ref: openair2/LAYER2/nr_pdcp/cucp_cuup_handler.c (e1_bearer_context_setup
at L162 — each entry corresponds to one DRB created via E1 Bearer Context Setup).
"""
from __future__ import annotations

from django.db import models


class Drb(models.Model):
    id = models.AutoField(primary_key=True)
    drb_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    ue_id = models.CharField(max_length=64, db_index=True)
    drb_id = models.IntegerField()  # 1..32
    qos_5qi = models.IntegerField()
    rlc_mode = models.CharField(max_length=4, default="AM")

    gtp_teid_ul = models.BigIntegerField()  # CU-UP allocates (DU sends here)
    gtp_teid_dl = models.BigIntegerField()  # peer DU TEID (set after F1 UE Ctx Setup Resp)

    dl_packets = models.BigIntegerField(default=0)
    ul_packets = models.BigIntegerField(default=0)

    created_at = models.DateTimeField()

    class Meta:
        app_label = "cu_up"
        db_table = "cu_up_drb"
        unique_together = (("ue_id", "drb_id"),)
        ordering = ("ue_id", "drb_id")
