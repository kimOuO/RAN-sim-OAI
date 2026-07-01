"""scenario_store 路由 — 路徑刻意與 Omniverse ran app 逐字相同,
讓消費端把 base URL 從 Omniverse 改指到 Physics 即可無痛切換。
掛在 /api/v0.1/ 下(main/urls.py include)。
"""
from django.urls import path

from main.apps.scenario_store.actors.scenario_actor import ScenarioController
from main.apps.scenario_store.actors.scene_reader_actor import (
    BuildingController,
    GNBReader,
    SceneLayoutReader,
    UEReader,
)

urlpatterns = [
    # ── Scenario CRUD(鏡像 Omniverse ScenarioController)──
    path("RAN/Scenario/ScenarioController/upload", ScenarioController.upload, name="ss_scenario_upload"),
    path("RAN/Scenario/ScenarioController/list", ScenarioController.list, name="ss_scenario_list"),
    path("RAN/Scenario/ScenarioController/read", ScenarioController.read, name="ss_scenario_read"),
    path("RAN/Scenario/ScenarioController/delete", ScenarioController.delete, name="ss_scenario_delete"),
    path("RAN/Scenario/ScenarioController/apply_to_scene", ScenarioController.apply_to_scene, name="ss_scenario_apply"),
    path("RAN/Scenario/ScenarioController/precompute", ScenarioController.precompute, name="ss_scenario_precompute"),
    path("RAN/Scenario/ScenarioController/update_status", ScenarioController.update_status, name="ss_scenario_update_status"),
    # ── Scene readers(鏡像 Omniverse GNBReader / UEReader / BuildingController / SceneLayoutReader)──
    path("RAN/GNB/GNBReader/read", GNBReader.read, name="ss_gnb_read"),
    path("RAN/UE/UEReader/read", UEReader.read, name="ss_ue_read"),
    path("RAN/Scene/BuildingController/read", BuildingController.read, name="ss_building_read"),
    path("RAN/Scene/SceneLayoutReader/read", SceneLayoutReader.read, name="ss_scene_layout_read"),
]
