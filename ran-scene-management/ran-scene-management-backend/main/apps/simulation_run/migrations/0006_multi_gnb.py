"""2026-09-27 多 gNB:SceneRun.e2_block / e2_nodes;RunInstance.name / gnb_uuid / du_uuid / e2_node_id。"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("simulation_run", "0005_scenerun_progress_sec")]

    operations = [
        migrations.AddField(model_name="scenerun", name="e2_block", field=models.IntegerField(blank=True, null=True)),
        migrations.AddField(model_name="scenerun", name="e2_nodes", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="runinstance", name="name", field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="runinstance", name="gnb_uuid",
                            field=models.CharField(blank=True, db_column="f_gnb_uuid", default="", max_length=255)),
        migrations.AddField(model_name="runinstance", name="du_uuid",
                            field=models.CharField(blank=True, db_column="f_du_uuid", default="", max_length=255)),
        migrations.AddField(model_name="runinstance", name="e2_node_id", field=models.CharField(blank=True, default="", max_length=64)),
    ]
