# 2026-09-27 多 gNB(C14):事件帶 gNB / E2 node。
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("run_telemetry_archive", "0005_run_pm_snapshot"),
    ]

    operations = [
        migrations.AddField(model_name="runhandoverevent", name="node_id",
                            field=models.CharField(blank=True, db_index=True, default="", max_length=128)),
        migrations.AddField(model_name="runhandoverevent", name="meid",
                            field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="runcontrolevent", name="node_id",
                            field=models.CharField(blank=True, db_index=True, default="", max_length=128)),
        migrations.AddField(model_name="runcontrolevent", name="meid",
                            field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="runpmsnapshot", name="node_id",
                            field=models.CharField(blank=True, db_index=True, default="", max_length=128)),
        migrations.AddField(model_name="runpmsnapshot", name="meid",
                            field=models.CharField(blank=True, default="", max_length=64)),
    ]
