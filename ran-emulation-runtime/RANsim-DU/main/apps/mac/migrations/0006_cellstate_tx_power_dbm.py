from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("mac", "0005_alter_cellstate_bw_mhz_alter_cellstate_total_prb")]

    operations = [
        migrations.AddField(
            model_name="cellstate",
            name="tx_power_dbm",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
