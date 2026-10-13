"""Xn 對端與外部鄰區表(多 gNB P6,TS 38.423 Xn Setup 交換的 served cells)。"""
from __future__ import annotations

from django.db import models


class XnPeer(models.Model):
    """鄰居 gNB(Xn-C 對端)。state:ESTABLISHED = Xn Setup 已完成。"""
    id = models.AutoField(primary_key=True)
    gnb_id = models.BigIntegerField(unique=True, db_index=True)
    gnb_name = models.CharField(max_length=128, blank=True, default="")
    cu_url = models.CharField(max_length=255, blank=True, default="")
    state = models.CharField(max_length=16, default="NONE")
    established_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField()

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_xn_peer"
        ordering = ("gnb_id",)


class XnNeighbourCell(models.Model):
    """鄰居 gNB 的 served cell。本 gNB 的 cell 在 CellConfig;換手、重建、ANR、ReportCGI、
    RC 3-1 目標解析遇到不是自己的 cell 就查這裡。"""
    id = models.AutoField(primary_key=True)
    cell_id = models.CharField(max_length=64, unique=True, db_index=True)
    gnb_id = models.BigIntegerField(db_index=True)
    nci = models.BigIntegerField(null=True, blank=True, db_index=True)
    pci = models.IntegerField(default=0)
    arfcn = models.IntegerField(default=0)
    frequency_ghz = models.FloatField(default=0.0)
    bandwidth_mhz = models.FloatField(default=0.0)
    plmn = models.CharField(max_length=16, blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_barred = models.BooleanField(default=False)
    updated_at = models.DateTimeField()

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_xn_neighbour_cell"
        ordering = ("cell_id",)
