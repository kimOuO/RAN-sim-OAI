# 2026-09-22:完整 PM 快照落地。full KPM 原本只經 E2 送 RIC,我方歸檔只留四個欄位,
# 外部 Agent 的 I-5 原始觀測(cell 級量測鍵)因此給不出來。

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('run_telemetry_archive', '0004_archive_ric_run')]

    operations = [
        migrations.CreateModel(
            name='RunPmSnapshot',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('run_pm_snapshot_uuid', models.CharField(db_index=True, max_length=255, unique=True)),
                ('run_seq', models.IntegerField(db_index=True, default=0)),
                ('ric_run', models.IntegerField(db_index=True, default=0)),
                ('f_scene_run_uuid', models.CharField(
                    db_index=True, max_length=255,
                    help_text='Reference to registry scene_run.scene_run_uuid')),
                ('at_sim_ms', models.BigIntegerField(blank=True, null=True)),
                ('wall_time_ms', models.BigIntegerField(default=0)),
                ('pm', models.JSONField(default=dict)),
                ('e2', models.JSONField(default=list)),
                ('warnings', models.JSONField(default=list)),
                ('run_pm_snapshot_created_at', models.DateTimeField()),
                ('run_pm_snapshot_updated_at', models.DateTimeField()),
            ],
            options={'db_table': 'run_telemetry_archive_run_pm_snapshot', 'ordering': ('id',)},
        ),
    ]
