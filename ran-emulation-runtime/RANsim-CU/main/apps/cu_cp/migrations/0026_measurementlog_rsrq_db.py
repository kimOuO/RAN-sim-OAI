# 2026-09-22:服務 cell 的 RSRQ(TS 38.215)。以前沒有這個欄位,鄰區的又固定 0.0。

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('cu_cp', '0025_scene_sim_ms')]
    operations = [
        migrations.AddField(model_name='measurementlog', name='rsrq_db',
                            field=models.FloatField(blank=True, null=True)),
    ]
