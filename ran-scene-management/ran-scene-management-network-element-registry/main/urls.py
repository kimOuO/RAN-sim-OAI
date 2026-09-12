"""URL = /api/v0.1/Network_element_registry/{Module}/{Component}/{Element}(backend_rule §7-1)。"""
from django.urls import include, path

urlpatterns = [
    path("api/v0.1/Network_element_registry/Preset_catalog/", include("main.apps.preset_catalog.api.urls")),
    path("api/v0.1/Network_element_registry/Scene_layout/", include("main.apps.scene_layout.api.urls")),
    path("api/v0.1/Network_element_registry/Radio_access_element/", include("main.apps.radio_access_element.api.urls")),
    path("api/v0.1/Network_element_registry/User_equipment/", include("main.apps.user_equipment.api.urls")),
    path("api/v0.1/Network_element_registry/Simulation_run/", include("main.apps.simulation_run.api.urls")),
]
