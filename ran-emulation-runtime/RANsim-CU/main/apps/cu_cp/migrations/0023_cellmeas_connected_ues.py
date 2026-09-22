# 2026-09-22:cell 量測報告帶上「掛在這個 cell 的 UE 數」。
# 歸檔端靠它分辨空視窗是「劇本上本來就沒人」還是「報告遺失」。

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cu_cp', '0022_meas_nullable_radio'),
    ]

    operations = [
        migrations.AddField(
            model_name='cellmeasurementlog',
            name='connected_ues',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
