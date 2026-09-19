"""du_config_template — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class DuConfigTemplate(models.Model):
    id = models.AutoField(primary_key=True)
    du_config_template_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=128, unique=True)
    tdd_pattern = models.CharField(max_length=32, default='DDDDDDDSUU')
    numerology = models.IntegerField(default=1)
    n_prb = models.IntegerField(default=106)
    min_prb = models.IntegerField(default=5)
    pf_alpha = models.FloatField(default=0.05)
    target_bler = models.FloatField(default=0.1)
    rlc_discard_timer_ms = models.IntegerField(default=300)
    rlc_tx_maxsize_bytes = models.IntegerField(default=10000000)
    harq_max_retx = models.IntegerField(default=4)
    # 2026-09-19:排程器(DU SIM_SCHEDULER);pf = 比例公平、rr = 輪流、max_thp = 最大吞吐
    scheduler = models.CharField(max_length=16, default='pf')
    qos_gbr_first = models.BooleanField(default=True)
    gbr_max_share = models.FloatField(default=0.3)
    du_config_template_created_at = models.DateTimeField()
    du_config_template_updated_at = models.DateTimeField()

    class Meta:
        app_label = "equipment_preset"
        db_table = "preset_catalog_du_config_template"
        ordering = ("id",)
