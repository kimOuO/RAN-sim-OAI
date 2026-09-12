"""Cell 元數據 — 每個 served cell 一筆。對應 OAI gNB_RrcConfigurationReq。"""
from django.db import models


class CellState(models.Model):
    id = models.AutoField(primary_key=True)
    cell_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    cell_id = models.CharField(max_length=64, unique=True, db_index=True)
    pci = models.IntegerField()
    total_prb = models.IntegerField(default=106)  # 40 MHz @ 30 kHz SCS (對齊 OAI band78)
    freq_ghz = models.FloatField(default=3.5)
    bw_mhz = models.FloatField(default=40.0)
    served_plmn = models.CharField(max_length=16, default="00101")
    # 2026-05-16 P2.9: OAI 真實 nr_cellid (36-bit int)。null → SHA-1 hash fallback。
    nr_cellid = models.BigIntegerField(null=True, blank=True, db_index=True)
    gnb_id = models.CharField(max_length=64, db_index=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    cell_created_at = models.BigIntegerField()
    cell_updated_at = models.BigIntegerField()

    class Meta:
        app_label = "mac"
        db_table = "mac_cell_state"
