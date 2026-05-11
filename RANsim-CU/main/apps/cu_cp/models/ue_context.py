"""UeContext — per-UE state in CU-CP. Mirrors OAI gNB_RRC_UE_t.

OAI ref: openair2/RRC/NR/nr_rrc_defs.h (gNB_RRC_UE_t at L172-253).
"""
from __future__ import annotations

from django.db import models


class UeContext(models.Model):
    RRC_STATES = (
        ("IDLE", "IDLE"),
        ("SETUP", "SETUP"),
        ("CONNECTED", "CONNECTED"),
        ("RELEASE", "RELEASE"),
        ("INACTIVE", "INACTIVE"),
    )

    id = models.AutoField(primary_key=True)
    ue_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    ue_id = models.CharField(max_length=64, unique=True, db_index=True)
    rrc_state = models.CharField(max_length=16, choices=RRC_STATES, default="IDLE")
    serving_cell = models.CharField(max_length=64, blank=True, default="")

    # Identifiers across interfaces (cf. OAI rrc_ue_id / amf_ue_ngap_id)
    rrc_ue_id = models.BigIntegerField(default=0)
    amf_ue_ngap_id = models.BigIntegerField(default=0)
    ran_ue_ngap_id = models.BigIntegerField(default=0)
    gnb_du_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    last_measurement_at = models.DateTimeField(null=True, blank=True)
    # Traffic profile (declarative spec, UE container reads + drives traffic generation).
    # Schema: {"pattern": "cbr"|"idle"|"bursty", "rate_mbps": float, "sdu_size": int, "bearer_id": int}
    traffic_profile_json = models.JSONField(blank=True, null=True, default=dict)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_ue_context"
        ordering = ("ue_id",)
