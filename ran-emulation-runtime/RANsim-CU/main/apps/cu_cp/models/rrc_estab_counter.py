"""RrcEstabCounter — per-cell RRC 連線建立「真累計」計數器(2026-08-12)。

修掉 ConnEstab 家族的現值代理:官方語意是歷史累計(每次 attach 事件 +1,只加不減)。
計數點 = ul_rrc_message 的 SETUP_REQUEST(Att)/ SETUP_COMPLETE(Succ)—— 真實事件。
HO 不動此計數(換手不是新的連線建立);重建走完整 attach 時會再計(語意正確)。
"""
from __future__ import annotations

from django.db import models


class RrcEstabCounter(models.Model):
    id = models.AutoField(primary_key=True)
    cell_id = models.CharField(max_length=64, unique=True, db_index=True)

    att = models.BigIntegerField(default=0)    # SETUP_REQUEST 次數(歷史累計)
    succ = models.BigIntegerField(default=0)   # SETUP_COMPLETE 次數

    updated_at = models.DateTimeField()

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_rrc_estab_counter"
