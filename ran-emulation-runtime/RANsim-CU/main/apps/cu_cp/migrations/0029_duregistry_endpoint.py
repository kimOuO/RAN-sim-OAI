# 2026-09-27 多 gNB:一個 CU 接多個 DU,記下每個 DU 的 F1 端點。
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cu_cp", "0028_cellconfig_tx_power_dbm"),
    ]

    operations = [
        migrations.AddField(
            model_name="duregistry",
            name="endpoint",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
