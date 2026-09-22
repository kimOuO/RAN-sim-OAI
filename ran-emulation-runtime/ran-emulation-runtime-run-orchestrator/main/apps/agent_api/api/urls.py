"""URL = /api/v0.1/Run_orchestrator/Agent_api/{Component}/{Element}(backend_rule §7-1)。

外部 Agent(情境問題庫系統)專用的唯讀 / 觸發介面,對應其需求規格 I-1~I-7。
"""
from django.urls import path

from main.apps.agent_api.actors.field_actor import FieldReader
from main.apps.agent_api.actors.run_actor import RunReader

urlpatterns = [
    # I-1 查詢場域清單
    path("FieldReader/list", FieldReader.list, name="agent_field_list"),
    # I-2 取得場域配置
    path("FieldReader/config", FieldReader.config, name="agent_field_config"),
    # I-4 查詢執行狀態
    path("RunReader/status", RunReader.status, name="agent_run_status"),
    # I-6 取得事件紀錄
    path("RunReader/events", RunReader.events, name="agent_run_events"),
    # I-7 取得組態變更紀錄
    path("RunReader/config_changes", RunReader.config_changes, name="agent_run_config_changes"),
]
