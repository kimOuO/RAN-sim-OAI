from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("field_scene", "0005_scene_e2_slot")]

    operations = [
        migrations.AddField(
            model_name="scene",
            name="category",
            field=models.CharField(blank=True, db_index=True, max_length=32, null=True),
        ),
    ]
