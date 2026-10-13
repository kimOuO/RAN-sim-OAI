"""2026-09-27 多 gNB:Cell.local_cell_id(gNB 內 0–16383)。既有 cell 依 id 順序在各自 gNB 內配 0, 1, 2…。"""
from django.db import migrations, models


def assign(apps, schema_editor):
    Cell = apps.get_model("equipment_ran", "Cell")
    counters: dict[str, int] = {}
    for c in Cell.objects.select_related("du").order_by("id"):
        g = c.du.gnb_id
        i = counters.get(g, 0)
        c.local_cell_id = i
        c.save(update_fields=["local_cell_id"])
        counters[g] = i + 1


class Migration(migrations.Migration):
    dependencies = [("equipment_ran", "0006_gnb_e2_index")]

    operations = [
        migrations.AddField(model_name="cell", name="local_cell_id", field=models.IntegerField(blank=True, null=True)),
        migrations.RunPython(assign, migrations.RunPython.noop),
    ]
