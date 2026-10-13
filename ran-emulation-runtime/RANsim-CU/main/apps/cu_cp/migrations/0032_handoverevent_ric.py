# 2026-09-27 多 gNB(C14):RIC 控制觸發的換手帶 RIC 的請求編號與標籤,供 RIC 對帳。
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cu_cp", "0031_xn"),
    ]

    operations = [
        migrations.AddField(model_name="handoverevent", name="ric_instance_id",
                            field=models.BigIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="handoverevent", name="ric_label",
                            field=models.CharField(blank=True, default="", max_length=255)),
    ]
