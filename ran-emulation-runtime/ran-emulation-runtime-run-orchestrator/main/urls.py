"""URL = /api/v0.1/Run_orchestrator/{Module}/{Component}/{Element}(backend_rule §7-1)。"""
from django.urls import include, path

urlpatterns = [
    path("api/v0.1/Run_orchestrator/Run_lifecycle/", include("main.apps.run_lifecycle.api.urls")),
    path("api/v0.1/Run_orchestrator/Run_telemetry_archive/", include("main.apps.run_telemetry_archive.api.urls")),
]
