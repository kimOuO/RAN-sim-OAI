"""RuState — RU 端 SFN/slot counter 等執行時狀態（singleton）。

對 OAI 的 RU_proc_t（defs_RU.h:194）— 只記必要的 frame counter，不真做 PHY 處理。
"""
from django.db import models


class RuState(models.Model):
    id = models.AutoField(primary_key=True)
    ru_state_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    sfn_counter = models.IntegerField(default=0)        # 0~1023
    slot_counter = models.IntegerField(default=0)       # 0~19 (numerology=1)
    numerology = models.IntegerField(default=1)
    fft_size = models.IntegerField(default=4096)
    cp_type = models.CharField(max_length=16, default="normal")

    last_tick_at = models.DateTimeField(null=True, blank=True)
    ru_state_created_at = models.DateTimeField()
    ru_state_updated_at = models.DateTimeField()

    class Meta:
        db_table = "ru_state"
