"""2026-09-27 多 gNB:Gnb.e2_index(場景內 0–15,唯一)。既有 gNB 依 id 順序配 0, 1, 2…。"""
import django.core.validators
from django.db import migrations, models


def assign_indexes(apps, schema_editor):
    Gnb = apps.get_model("equipment_ran", "Gnb")
    counters: dict[str, int] = {}
    for g in Gnb.objects.order_by("id"):
        key = g.scene_id
        i = counters.get(key, 0)
        if i <= 15:
            g.e2_index = i
            g.save(update_fields=["e2_index"])
        counters[key] = i + 1


class Migration(migrations.Migration):
    dependencies = [("equipment_ran", "0005_alter_cell_du_alter_du_config_template_alter_du_gnb_and_more")]

    operations = [
        migrations.AddField(
            model_name="gnb", name="e2_index",
            field=models.IntegerField(blank=True, null=True, validators=[
                django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(15)]),
        ),
        migrations.RunPython(assign_indexes, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="gnb",
            constraint=models.UniqueConstraint(fields=("scene", "e2_index"), name="uniq_gnb_e2_index_per_scene"),
        ),
    ]
