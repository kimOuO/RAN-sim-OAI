"""DuRegistry — DU registered via F1 Setup. Mirrors OAI's nr_rrc_du_container_t.

OAI ref: openair2/RRC/NR/rrc_gNB_du.c (struct nr_rrc_du_container_t).
"""
from __future__ import annotations

from django.db import models


class DuRegistry(models.Model):
    id = models.AutoField(primary_key=True)
    du_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    gnb_du_id = models.BigIntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255, blank=True, default="")
    served_cells_json = models.JSONField(default=list)

    registered_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_du_registry"
        ordering = ("gnb_du_id",)

    def __str__(self) -> str:
        return f"DU#{self.gnb_du_id}({self.name})"
