# 2026-09-27 多 gNB P6:Xn 對端 / 外部鄰區表;換手事件 C14 欄位;UE 的跨 gNB 換手來源(MRO)。
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cu_cp", "0030_handoverevent_ho_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="XnPeer",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("gnb_id", models.BigIntegerField(db_index=True, unique=True)),
                ("gnb_name", models.CharField(blank=True, default="", max_length=128)),
                ("cu_url", models.CharField(blank=True, default="", max_length=255)),
                ("state", models.CharField(default="NONE", max_length=16)),
                ("established_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField()),
            ],
            options={"db_table": "cu_cp_xn_peer", "ordering": ("gnb_id",)},
        ),
        migrations.CreateModel(
            name="XnNeighbourCell",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("cell_id", models.CharField(db_index=True, max_length=64, unique=True)),
                ("gnb_id", models.BigIntegerField(db_index=True)),
                ("nci", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("pci", models.IntegerField(default=0)),
                ("arfcn", models.IntegerField(default=0)),
                ("frequency_ghz", models.FloatField(default=0.0)),
                ("bandwidth_mhz", models.FloatField(default=0.0)),
                ("plmn", models.CharField(blank=True, default="", max_length=16)),
                ("is_active", models.BooleanField(default=True)),
                ("is_barred", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField()),
            ],
            options={"db_table": "cu_cp_xn_neighbour_cell", "ordering": ("cell_id",)},
        ),
        migrations.AddField(model_name="handoverevent", name="amf_ue_ngap_id",
                            field=models.BigIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="handoverevent", name="source_ncgi",
                            field=models.CharField(blank=True, default="", max_length=32)),
        migrations.AddField(model_name="handoverevent", name="target_ncgi",
                            field=models.CharField(blank=True, default="", max_length=32)),
        migrations.AddField(model_name="uecontext", name="last_ho_source_gnb",
                            field=models.BigIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="uecontext", name="last_ho_source_cell",
                            field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="uecontext", name="last_ho_uuid",
                            field=models.CharField(blank=True, default="", max_length=255)),
        migrations.AddField(model_name="uecontext", name="last_ho_at",
                            field=models.DateTimeField(blank=True, null=True)),
    ]
