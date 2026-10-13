"""run_instance — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class RunInstance(models.Model):
    id = models.AutoField(primary_key=True)
    run_instance_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    scene_run = models.ForeignKey("simulation_run.SceneRun", on_delete=models.CASCADE, to_field="scene_run_uuid", db_column="f_scene_run_uuid", related_name="instances", db_index=True)
    role = models.CharField(max_length=16)   # amf / cu / du / ru / ue / e2adapter
    # 2026-09-27 多 gNB:同一角色可有多個實例(每個 gNB 一個 CU、e2adapter;每個 DU 一個 DU 容器)。
    name = models.CharField(max_length=64, blank=True, default='')        # 容器名,例 cu-<rid>-src
    gnb_uuid = models.CharField(max_length=255, blank=True, default='', db_column="f_gnb_uuid")   # cu / du / e2adapter 所屬 gNB
    du_uuid = models.CharField(max_length=255, blank=True, default='', db_column="f_du_uuid")     # du 對應的 registry DU
    e2_node_id = models.CharField(max_length=64, blank=True, default='')  # cu / e2adapter 的 meid
    container_id = models.CharField(max_length=128, blank=True, default='')
    host_port = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, default='pending')
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    # 依賴鏈健康(2026-09-15):status=degraded 時的原因,如「sim CU 不可達」「SCTP 斷線」;正常為空
    health_detail = models.CharField(max_length=255, blank=True, default='')
    run_instance_created_at = models.DateTimeField()
    run_instance_updated_at = models.DateTimeField()

    class Meta:
        app_label = "simulation_run"
        db_table = "simulation_run_run_instance"
        ordering = ("id",)
