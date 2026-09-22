from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("cu_cp", "0027_measurementlog_cqi")]

    operations = [
        migrations.AddField(
            model_name="cellconfig",
            name="tx_power_dbm",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
