"""每個 UE 在 MAC 層的 snapshot — Tick runner 每 N tick flush 一次。"""
from django.db import models


class UeMacState(models.Model):
    id = models.AutoField(primary_key=True)
    ue_mac_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    ue_id = models.CharField(max_length=64, unique=True, db_index=True)
    serving_cell_id = models.CharField(max_length=64, db_index=True)

    last_mcs_dl = models.IntegerField(default=9)
    last_mcs_ul = models.IntegerField(default=9)
    last_cqi = models.IntegerField(default=7)
    last_sinr_db = models.FloatField(default=0.0)
    last_pmi = models.IntegerField(default=0)
    last_rank = models.IntegerField(default=1)
    last_allocated_prb_dl = models.IntegerField(default=0)
    last_allocated_prb_ul = models.IntegerField(default=0)

    ue_mac_created_at = models.BigIntegerField()
    ue_mac_updated_at = models.BigIntegerField()

    class Meta:
        app_label = "mac"
        db_table = "mac_ue_state"
