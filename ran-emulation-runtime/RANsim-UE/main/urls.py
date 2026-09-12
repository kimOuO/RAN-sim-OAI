"""URL: /api/v0.1/UE/<Component>/<Element>"""
from django.urls import include, path

urlpatterns = [
    path("api/v0.1/UE/", include("main.apps.ue_lifecycle.api.urls")),
    path("api/v0.1/UE/Scenario/", include("main.apps.scenario.api.urls")),
    path("api/v0.1/UE/Sim/", include("main.apps.scenario.api.sim_urls")),
]
