"""TickState — 單例 row,記錄 tick 累積/sfn/slot/啟動時間。"""
from django.db import models


class TickState(models.Model):
    id = models.AutoField(primary_key=True)
    tick_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    tick_count = models.BigIntegerField(default=0)
    sfn = models.IntegerField(default=0)  # 0..1023
    slot = models.IntegerField(default=0)  # 0..19
    started_at_ms = models.BigIntegerField(null=True)
    last_tick_ms = models.BigIntegerField(default=0)
    is_running = models.BooleanField(default=False)
    tick_state_updated_at = models.BigIntegerField()

    class Meta:
        app_label = "tick"
        db_table = "tick_state"
