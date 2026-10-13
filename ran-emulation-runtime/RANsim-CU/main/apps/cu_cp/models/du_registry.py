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
    # 多 gNB(2026-09-27):DU 的 F1 端點(F1 Setup 帶上來)。一個 CU 接多個 DU 時,
    # UE Context Setup / Modification / Release、DL RRC 都依 UE 或 cell 所在的 DU 送到這裡。
    endpoint = models.CharField(max_length=255, blank=True, default="")

    registered_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_du_registry"
        ordering = ("gnb_du_id",)

    def __str__(self) -> str:
        return f"DU#{self.gnb_du_id}({self.name})"
