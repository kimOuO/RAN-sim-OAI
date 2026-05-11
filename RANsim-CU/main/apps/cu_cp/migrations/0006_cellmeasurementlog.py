# AL2 — CellMeasurementLog for cell-level RRU.PrbTotDl (3GPP TS 28.552)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cu_cp', '0005_uecontext_traffic_profile_json'),
    ]

    operations = [
        migrations.CreateModel(
            name='CellMeasurementLog',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('cell_id', models.CharField(db_index=True, max_length=64)),
                ('prb_pct_dl', models.FloatField(default=0.0)),
                ('prb_pct_ul', models.FloatField(default=0.0)),
                ('tick_count', models.IntegerField(default=0)),
                ('window_seconds', models.FloatField(default=0.0)),
                ('recorded_at', models.DateTimeField(db_index=True)),
            ],
            options={
                'db_table': 'cu_cp_cell_measurement_log',
                'ordering': ('-recorded_at',),
            },
        ),
    ]
