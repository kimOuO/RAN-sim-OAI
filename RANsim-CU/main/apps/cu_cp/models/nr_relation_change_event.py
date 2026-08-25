"""NrRelationChangeEvent — ANR 關係變更審計(9.3.38 relationChangeEvents 資料源)。

每次 SON 觸發(ADD/REMOVE/FLAG)成功變更 NRT 就落一筆。P0-5(2026-08-11)。
"""
from __future__ import annotations

from django.db import models


class NrRelationChangeEvent(models.Model):
    id = models.AutoField(primary_key=True)

    action = models.CharField(max_length=16)            # ADD / REMOVE / FLAG / SEED
    source_cell_id = models.CharField(max_length=64, db_index=True)
    target_cgi = models.CharField(max_length=64)
    by = models.CharField(max_length=32, default="xapp")  # xapp / seeder / manual
    detail = models.CharField(max_length=128, blank=True, default="")
    at = models.DateTimeField(db_index=True)

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_nr_relation_change_event"
        ordering = ("-at",)
