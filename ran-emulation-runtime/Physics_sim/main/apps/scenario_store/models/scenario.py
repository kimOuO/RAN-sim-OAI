"""Scenario — physics_db 上的劇本倉庫,鏡像 Omniverse ran.Scenario。

讓 RAN sim 可脫離 Omniverse:劇本 raw_json 存這裡,消費端(UE scenario_loader /
precompute)把來源 URL 指到 Physics 就能取得相同資料。
欄位刻意與 Omniverse Scenario 一致,回應形狀才能逐字相同。
"""
from django.db import models


class Scenario(models.Model):
    id = models.AutoField(primary_key=True)
    scenario_id = models.CharField(max_length=128, unique=True, db_index=True)
    scene_id = models.CharField(max_length=128, db_index=True)
    raw_json = models.JSONField(default=dict)
    duration_sec = models.FloatField(default=0.0)
    tick_ms = models.IntegerField(default=500)
    ue_count = models.IntegerField(default=0)
    # precompute 狀態(precompute worker 會回寫)
    precompute_status = models.CharField(max_length=32, default="pending", db_index=True)
    precompute_progress = models.FloatField(default=0.0)
    precompute_error = models.TextField(blank=True, default="")
    cache_path = models.CharField(max_length=512, blank=True, default="")
    cache_size_bytes = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "scenario_store"
        db_table = "scenario"
        ordering = ("-created_at",)
