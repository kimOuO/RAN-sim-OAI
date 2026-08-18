from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cu_cp", "0013_cellcumcounter_measurementlog_qos_5qi"),
    ]

    operations = [
        migrations.AddField(
            model_name="cellconfig",
            name="is_barred",
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]
