from django.urls import path
from main.apps.scene_layout.actors.scenario_importer_actor import ScenarioImporter
from main.apps.scene_layout.actors.scene_actor import SceneController, SceneReader
from main.apps.scene_layout.actors.building_actor import BuildingController, BuildingReader

urlpatterns = [
    path("ScenarioImporter/import_v1", ScenarioImporter.import_v1, name="scenario_import_v1"),
    path("ScenarioImporter/export_v1", ScenarioImporter.export_v1, name="scenario_export_v1"),
    path("SceneController/create", SceneController.create, name="scene_create"),
    path("SceneController/update", SceneController.update, name="scene_update"),
    path("SceneController/delete", SceneController.delete, name="scene_delete"),
    path("SceneReader/read", SceneReader.read, name="scene_read"),
    path("SceneReader/read_full_tree", SceneReader.read_full_tree, name="scene_read_full_tree"),
    path("BuildingController/create", BuildingController.create, name="building_create"),
    path("BuildingController/update", BuildingController.update, name="building_update"),
    path("BuildingController/delete", BuildingController.delete, name="building_delete"),
    path("BuildingReader/read", BuildingReader.read, name="building_read"),
]
