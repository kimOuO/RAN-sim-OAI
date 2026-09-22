"""URL = /api/v0.1/Run_orchestrator/{Module}/{Component}/{Element}(backend_rule §7-1)。"""
from django.urls import include, path

from main.apps.run_lifecycle.api.status_view import status

urlpatterns = [
    # 給 RIC 端維運腳本的唯讀狀態查詢(不走 backend_rule §7-1 的命名,刻意保持最短)
    path("status", status, name="status"),
    path("api/v0.1/Run_orchestrator/Run_lifecycle/", include("main.apps.run_lifecycle.api.urls")),
    path("api/v0.1/Run_orchestrator/Run_telemetry_archive/", include("main.apps.run_telemetry_archive.api.urls")),
    # 外部 Agent(情境問題庫系統)的介面 I-1~I-7
    path("api/v0.1/Run_orchestrator/Agent_api/", include("main.apps.agent_api.api.urls")),
]
