# 2026-09-27 多 gNB(C14):換手種類。
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cu_cp", "0029_duregistry_endpoint"),
    ]

    operations = [
        migrations.AddField(
            model_name="handoverevent",
            name="ho_type",
            field=models.CharField(blank=True, default="intra-DU", max_length=16),
        ),
    ]
