"""URL = /api/v0.1/Building_geometry_ingest/{Module}/{Component}/{Element}。"""
from django.urls import include, path

urlpatterns = [
    path("api/v0.1/Building_geometry_ingest/Scan_mesh_ingest/", include("main.apps.scan_mesh_ingest.api.urls")),
    path("api/v0.1/Building_geometry_ingest/Osm_footprint_ingest/", include("main.apps.osm_footprint_ingest.api.urls")),
]
