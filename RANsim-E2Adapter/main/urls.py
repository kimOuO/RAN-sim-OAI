"""Top-level URL aggregation. Per backend_rule.md §3-2-2: only `include(...)`."""
from django.urls import include, path

urlpatterns = [
    path("api/v0.1/E2Adapter/", include("main.apps.e2_adapter.api.urls")),
]
