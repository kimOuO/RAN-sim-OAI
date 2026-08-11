"""NrCellRelation — ANR / NCRT 鄰區關係表(受控物件).

對應 E2SM-RC §9.3.38 Neighbour Cell Relation IE + 卷面延伸欄位(ANR 情境 v8):
xApp 經 E2SM-ANR 的 ADD/REMOVE/FLAG 觸發函式操作本表條目;`version` 為
confirm 慣用式的生效判定載體(每次變更 +1)。
"""
from __future__ import annotations

from django.db import models


class NrCellRelation(models.Model):
    id = models.AutoField(primary_key=True)

    # 關係識別 —— source(本網轄下 cell) → target(鄰區 CGI)
    source_cell_id = models.CharField(max_length=64, db_index=True)
    target_cgi = models.CharField(max_length=64, db_index=True)

    # §9.3.38 目標識別
    target_pci = models.IntegerField()
    target_arfcn = models.IntegerField()
    target_rat = models.CharField(max_length=8, default="NR")
    target_plmn = models.CharField(max_length=16, default="")

    # 卷面延伸欄位(管理面視圖;E2 視圖假設可見)
    is_ho_allowed = models.BooleanField(default=True)
    is_remove_allowed = models.BooleanField(default=True)
    is_xn_allowed = models.BooleanField(default=True)

    # §9.3.38 正式欄位
    xn_x2_established = models.BooleanField(default=False)
    ho_validated = models.BooleanField(default=False)
    version = models.IntegerField(default=1)  # 每次變更 +1 → confirm 載體

    # 旗標(封而不刪;28.313 §6.4.1.3.5)—— A 級行為由 A3 換手讀取
    ho_blocklist = models.BooleanField(default=False)
    no_remove = models.BooleanField(default=False)
    xn_blocklist = models.BooleanField(default=False)

    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_nr_cell_relation"
        unique_together = (("source_cell_id", "target_cgi"),)
        ordering = ("source_cell_id", "target_cgi")
