"""run_pm_snapshot — 完整 PM 快照(322 鍵)的落地。

為什麼要單獨一張表:full KPM 一直只經 E2 送給 RIC,我方自己的歸檔只留了
prb_pct_dl / prb_pct_ul / window_seconds / connected_ues 四個欄位。
外部 Agent 的 I-5「原始觀測」要的是完整的 cell 級量測鍵,沒有落地就給不出來。

不併進 RunKpmSample 的理由:
  - 取樣節奏不同。RunKpmSample 是每個 PM 視窗一列(1 秒);這裡是每個輪詢週期
    一份快照(預設 2 秒),兩者對不齊,硬塞會讓人以為每個視窗都有完整 PM。
  - 體積差很多。一份快照是 322 鍵 × cell 數,不該讓每個視窗都揹著。

一個 table 一個檔案(backend_rule §5-1)。
"""
from django.db import models


class RunPmSnapshot(models.Model):
    id = models.AutoField(primary_key=True)
    run_pm_snapshot_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    run_seq = models.IntegerField(default=0, db_index=True)
    ric_run = models.IntegerField(default=0, db_index=True)
    f_scene_run_uuid = models.CharField(max_length=255, db_index=True,
                                        help_text='Reference to registry scene_run.scene_run_uuid')
    # 劇本時間(取自最近一次 DU 報告的 scene clock);null = 還沒收到過報告
    at_sim_ms = models.BigIntegerField(null=True, blank=True)
    wall_time_ms = models.BigIntegerField(default=0)
    # {gnb_id: [ {cell_id, ...322 鍵...}, ... ]}
    pm = models.JSONField(default=dict)
    # e2 區塊(逐 UE 量測)與 warnings,原樣保留
    e2 = models.JSONField(default=list)
    warnings = models.JSONField(default=list)
    # 多 gNB(2026-09-27,介面 C14):事件來自哪個 gNB(= RIC 的 nodeId)與它的 E2 node(meid)。舊資料空字串。
    node_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    meid = models.CharField(max_length=64, blank=True, default="")
    run_pm_snapshot_created_at = models.DateTimeField()
    run_pm_snapshot_updated_at = models.DateTimeField()

    class Meta:
        app_label = "run_telemetry_archive"
        db_table = "run_telemetry_archive_run_pm_snapshot"
        ordering = ("id",)
