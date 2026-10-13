"""場次狀態收成三種(2026-09-28):idle / precomputing / running;上一次結果另存 last_result。"""
from django.db import migrations, models

_RESULT = {"done": "done", "stopped": "stopped", "failed": "failed"}


def forward(apps, schema_editor):
    SceneRun = apps.get_model("simulation_run", "SceneRun")
    for r in SceneRun.objects.all():
        old = r.status or ""
        new = "running" if old in ("running", "starting") else ("precomputing" if old == "precomputing" else "idle")
        r.last_result = _RESULT.get(old, r.last_result or "")
        r.status = new
        r.save(update_fields=["status", "last_result"])


def backward(apps, schema_editor):
    SceneRun = apps.get_model("simulation_run", "SceneRun")
    for r in SceneRun.objects.all():
        if r.status == "idle":
            r.status = r.last_result or ("ready" if r.cache_path else "draft")
            r.save(update_fields=["status"])


class Migration(migrations.Migration):
    dependencies = [("simulation_run", "0006_multi_gnb")]
    operations = [
        migrations.AddField(model_name="scenerun", name="last_result",
                            field=models.CharField(blank=True, default="", max_length=16)),
        migrations.AlterField(model_name="scenerun", name="status",
                              field=models.CharField(default="idle", max_length=16)),
        migrations.RunPython(forward, backward),
    ]
