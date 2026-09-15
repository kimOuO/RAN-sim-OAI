"""URL = /api/v0.1/Scene_management_backend/{Module}/{Component}/{Element}(backend_rule §7-1)。"""
from django.urls import include, path

from main.apps.field_scene.actors.legacy_scenario_store_actor import LegacyScenarioStore

urlpatterns = [
    # ★ 過渡用相容端點(舊劇本倉庫路徑;P2 刪除)。見 legacy_scenario_store_actor.py
    path("api/v0.1/RAN/Scenario/ScenarioController/read", LegacyScenarioStore.read, name="legacy_scenario_read"),
    path("api/v0.1/RAN/Scenario/ScenarioController/list", LegacyScenarioStore.list, name="legacy_scenario_list"),
    path("api/v0.1/Scene_management_backend/Equipment_preset/", include("main.apps.equipment_preset.api.urls")),
    path("api/v0.1/Scene_management_backend/Field_scene/", include("main.apps.field_scene.api.urls")),
    path("api/v0.1/Scene_management_backend/Equipment_ran/", include("main.apps.equipment_ran.api.urls")),
    path("api/v0.1/Scene_management_backend/Equipment_ue/", include("main.apps.equipment_ue.api.urls")),
    path("api/v0.1/Scene_management_backend/Simulation_run/", include("main.apps.simulation_run.api.urls")),
    path("api/v0.1/Scene_management_backend/Render_scan_mesh/", include("main.apps.render_scan_mesh.api.urls")),
    path("api/v0.1/Scene_management_backend/Render_osm_footprint/", include("main.apps.render_osm_footprint.api.urls")),
]
