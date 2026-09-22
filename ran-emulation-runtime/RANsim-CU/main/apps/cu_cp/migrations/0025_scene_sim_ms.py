# 2026-09-22:量測與事件都帶上劇本時鐘。
# 原本歸檔是把各視窗的 tick_count 累加來推算劇本時間,報告一掉就失真
# (實測 8h 劇本一場少算 59%、另一場多算 12%);事件更是一律填 0。
# DU 的 scene_tick × sim_dt_ms 是定義值(cached 通道查表的索引),直接帶下來即可。

from django.db import migrations, models


def _f():
    return models.BigIntegerField(blank=True, null=True)


class Migration(migrations.Migration):

    dependencies = [
        ('cu_cp', '0024_son_action_log'),
    ]

    operations = [
        migrations.AddField(model_name='measurementlog', name='scene_sim_ms', field=_f()),
        migrations.AddField(model_name='cellmeasurementlog', name='scene_sim_ms', field=_f()),
        migrations.AddField(model_name='handoverevent', name='scene_sim_ms', field=_f()),
        migrations.AddField(model_name='rlfevent', name='scene_sim_ms', field=_f()),
    ]
