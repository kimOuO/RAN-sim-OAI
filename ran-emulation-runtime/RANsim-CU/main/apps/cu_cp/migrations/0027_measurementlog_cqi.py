# 2026-09-22:逐 UE 的寬頻 CQI(規格 I-5 建議欄位)。RU 本來就算,DU 收到只拿去調 MCS。

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('cu_cp', '0026_measurementlog_rsrq_db')]
    operations = [
        migrations.AddField(model_name='measurementlog', name='cqi',
                            field=models.FloatField(blank=True, null=True)),
    ]
