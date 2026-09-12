"""E2 訂閱持久化 — 2026-08-26「CU 重啟⇒斷流」三層根因修復之層 1。

subscription_registry 是 in-memory singleton,CU 重啟訂閱蒸發 → adapter 走
Y1(登錄空→E2 Reset→RIC 重訂)補救,但實測常斷到人工重訂。
此表讓訂閱跨重啟存活:create/delete 同步寫,啟動時回載進 singleton。
indication buffer 不落地(丟了無妨,下一週期重生)。
"""
from django.db import models


class E2Subscription(models.Model):
    subscription_id = models.CharField(max_length=64, primary_key=True)
    service_model = models.CharField(max_length=16)          # 'KPM' | 'RC' | ...
    ran_function_id = models.IntegerField()
    action_definition = models.JSONField(default=dict)
    event_trigger = models.JSONField(default=dict)
    ric_req_id = models.JSONField(default=dict)
    created_at_ms = models.BigIntegerField(default=0)
    status = models.CharField(max_length=16, default="active")

    class Meta:
        app_label = "cu_cp"
        db_table = "cu_e2_subscription"
