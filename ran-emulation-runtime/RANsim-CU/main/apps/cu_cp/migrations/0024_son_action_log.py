# 2026-09-22:自主(非 RIC 觸發)的組態變更稽核,供 Agent 介面 I-7 區分事件來源。

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cu_cp', '0023_cellmeas_connected_ues'),
    ]

    operations = [
        migrations.CreateModel(
            name='SonActionLog',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('object_type', models.CharField(max_length=32)),
                ('object_id', models.CharField(db_index=True, max_length=160)),
                ('action', models.CharField(max_length=32)),
                ('attribute', models.CharField(blank=True, default='', max_length=64)),
                ('before', models.CharField(blank=True, default='', max_length=128)),
                ('after', models.CharField(blank=True, default='', max_length=128)),
                ('function', models.CharField(default='anr_auto', max_length=32)),
                ('reason', models.CharField(blank=True, default='', max_length=200)),
                ('recorded_at', models.DateTimeField(db_index=True)),
            ],
            options={'db_table': 'cu_cp_son_action_log', 'ordering': ('id',)},
        ),
    ]
