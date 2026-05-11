"""URL: /api/v0.1/UE/<Component>/<Element>"""
from django.urls import include, path

urlpatterns = [
    path("api/v0.1/UE/", include("main.apps.ue_lifecycle.api.urls")),
]
