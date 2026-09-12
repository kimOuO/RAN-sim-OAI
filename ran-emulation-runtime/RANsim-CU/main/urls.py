"""Main URL aggregation. Both apps mount under /api/v0.1/CU/."""
from django.urls import include, path

urlpatterns = [
    path("api/v0.1/CU/", include("main.apps.cu_cp.api.urls")),
    path("api/v0.1/CU/", include("main.apps.cu_up.api.urls")),
]
