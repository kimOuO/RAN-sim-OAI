"""CellCumCounter — per-cell 持久累計計數(A/B/C 修復,2026-08-12)。

修掉三個「可修但未修」的記錄缺口:
  A. session_time_sec:已釋放 session 的存活秒數累計(釋放/掉話時落帳)。
     SessionTime 總值 = 本表累計 + 當下連線中 UE 的 Σ(now−created_at)。
  B. conn_max:連線數歷史高水位 —— 持久化,CU 重啟不歸零。
  C. conn_sum / conn_n:連線數取樣累計 → ConnMean = sum/n(真平均,非瞬時值)。
"""
from __future__ import annotations

from django.db import models


class CellCumCounter(models.Model):
    id = models.AutoField(primary_key=True)
    cell_id = models.CharField(max_length=64, unique=True, db_index=True)

    session_time_sec = models.BigIntegerField(default=0)   # A:已釋放 session 秒數累計
    conn_max = models.IntegerField(default=0)              # B:連線數高水位(持久)
    conn_sum = models.BigIntegerField(default=0)           # C:取樣加總
    conn_n = models.BigIntegerField(default=0)             # C:取樣次數

    updated_at = models.DateTimeField()

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_cp_cell_cum_counter"
