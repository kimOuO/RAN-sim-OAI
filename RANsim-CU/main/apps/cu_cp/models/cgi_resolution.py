"""CgiResolution — (PCI, ARFCN) → CGI 解析表.

給 E2SM-RC CONTROL Style 9 (RC_MEASCONFIG_REPORTCGI):xApp 以 UE 量測回報的
PCI+ARFCN 反查全域 CGI。sim 從 CellConfig 種子(本網 cell 的 pci/arfcn → cell_id)。
"""
from __future__ import annotations

from django.db import models


class CgiResolution(models.Model):
    id = models.AutoField(primary_key=True)

    pci = models.IntegerField(db_index=True)
    arfcn = models.IntegerField(db_index=True)

    cgi = models.CharField(max_length=64)
    plmn = models.CharField(max_length=16, default="")

    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_cgi_resolution"
        unique_together = (("pci", "arfcn"),)
        ordering = ("pci", "arfcn")
