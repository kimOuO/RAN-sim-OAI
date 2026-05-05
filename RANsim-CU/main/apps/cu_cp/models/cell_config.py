"""CellConfig — one cell served by a DU."""
from __future__ import annotations

from django.db import models


class CellConfig(models.Model):
    id = models.AutoField(primary_key=True)
    cell_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    cell_id = models.CharField(max_length=64, unique=True, db_index=True)
    pci = models.IntegerField()
    frequency_ghz = models.FloatField()
    bandwidth_mhz = models.FloatField()
    served_plmn = models.CharField(max_length=16, default="00101")

    # Cross-table reference to DuRegistry.gnb_du_id (kept as plain int — not FK
    # because we may onboard DUs lazily before their cells are registered).
    served_by_du_id = models.BigIntegerField(db_index=True)

    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_cell_config"
        ordering = ("cell_id",)
