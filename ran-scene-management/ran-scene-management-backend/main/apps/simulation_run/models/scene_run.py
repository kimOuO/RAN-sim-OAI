"""scene_run — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class SceneRun(models.Model):
    id = models.AutoField(primary_key=True)
    scene_run_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    scene = models.ForeignKey("field_scene.Scene", on_delete=models.CASCADE, to_field="scene_uuid", db_column="f_scene_uuid", related_name="runs", db_index=True)
    mode = models.CharField(max_length=8, default='cached')
    speed_x = models.FloatField(default=1.0)
    sim_dt_ms = models.IntegerField(default=500)
    duration_sec = models.IntegerField(default=60)
    # 2026-09-28:狀態只有三種 —— idle(閒置、可啟動)/ precomputing(預算通道中)/ running(執行中)。
    # 「有沒有預算」看 cache_path(不是狀態);上一次跑的結果另存 last_result。
    status = models.CharField(max_length=16, default='idle')
    # 上一次執行怎麼結束:done(劇本跑完)/ stopped(人為或外部中止)/ failed(起不來或中途失敗);沒跑過為空。
    # 外部 Agent 的 I-4 靠它分辨「可以取資料」與「要重跑」。
    last_result = models.CharField(max_length=16, blank=True, default='')
    cache_path = models.CharField(max_length=512, blank=True, default='')
    # 2026-09-27 多 gNB:本場配到的 E2 區塊,與每個 gNB 的 E2 身分。
    # e2_nodes = [{gnb_uuid, node_id(= gNB 名), e2_index, slot, gnb_id_hex, e2_node_id(meid), cell_tag}, …]
    e2_block = models.IntegerField(null=True, blank=True)
    e2_nodes = models.JSONField(default=list, blank=True)
    # 以下兩欄是改版前「一場一個 E2 node」的欄位,過渡期保留(= e2_nodes[0]),orchestrator 改完後移除。
    gnb_id_hex = models.CharField(max_length=16, blank=True, default='')
    e2_node_id = models.CharField(max_length=64, blank=True, default='')
    snapshot_json = models.JSONField(null=True, blank=True)
    # 2026-09-22:已模擬秒數(DU 的劇本時鐘)。外部 Agent 的 I-4 要輪詢進度,
    # 我們自己的監控頁以前也只能去看 DU 容器 log 才知道跑到哪。
    progress_sec = models.FloatField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    scene_run_created_at = models.DateTimeField()
    scene_run_updated_at = models.DateTimeField()

    class Meta:
        app_label = "simulation_run"
        db_table = "simulation_run_scene_run"
        ordering = ("id",)
