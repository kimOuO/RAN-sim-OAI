"""URL: /api/v0.1/AMF/<Module>/<Component>/<Element>"""
from django.urls import include, path

urlpatterns = [
    path("api/v0.1/AMF/", include("main.apps.amf.api.urls")),
]
