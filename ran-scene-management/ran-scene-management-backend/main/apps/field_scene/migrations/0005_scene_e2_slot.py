# 2026-09-22:場域釘住 E2 槽位,讓 gNB ID 與 cell NCI 在啟動前就確定
# (外部 Agent 要拿這些識別去部署 xApp)。

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('field_scene', '0004_material_alter_building_scene_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='scene',
            name='e2_slot',
            field=models.IntegerField(blank=True, null=True, unique=True),
        ),
    ]
