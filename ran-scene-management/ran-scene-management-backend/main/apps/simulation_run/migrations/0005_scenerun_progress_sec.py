# 2026-09-22:run 記錄已模擬秒數,供 Agent 介面 I-4 輪詢進度與監控頁顯示。

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('simulation_run', '0004_alter_scenerun_scene'),
    ]

    operations = [
        migrations.AddField(
            model_name='scenerun',
            name='progress_sec',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
