"""2026-09-27 多 gNB:Scene.e2_slot(單一槽位)→ e2_block(區塊,1–15)。既有釘選值 1–4 直接沿用為區塊號。"""
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("field_scene", "0006_scene_category")]

    operations = [
        migrations.RenameField(model_name="scene", old_name="e2_slot", new_name="e2_block"),
        migrations.AlterField(
            model_name="scene", name="e2_block",
            field=models.IntegerField(blank=True, null=True, unique=True, validators=[
                django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(15)]),
        ),
    ]
