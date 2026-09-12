# Generated 2026-05-16 — P2.4 nr_cellid column for OAI cell ID alignment.
# See docs/init_setting/alignment_action_plan.md Phase 2.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cu_cp', '0006_cellmeasurementlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='cellconfig',
            name='nr_cellid',
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
    ]
