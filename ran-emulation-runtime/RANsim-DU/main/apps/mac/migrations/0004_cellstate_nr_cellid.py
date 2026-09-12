# Generated 2026-05-16 — P2.9 nr_cellid column on DU side for OAI cell ID alignment.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mac', '0003_cellstate_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='cellstate',
            name='nr_cellid',
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
    ]
