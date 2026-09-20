from django.urls import path
from main.apps.field_scene.actors.scenario_importer_actor import ScenarioImporter
from main.apps.field_scene.actors.scene_actor import SceneController, SceneReader
from main.apps.field_scene.actors.building_actor import BuildingController, BuildingReader
from main.apps.field_scene.actors.material_actor import MaterialController, MaterialReader
from main.apps.field_scene.actors.scene_geometry_actor import SceneGeometryReader

urlpatterns = [
    path("ScenarioImporter/import_v1", ScenarioImporter.import_v1, name="scenario_import_v1"),
    path("ScenarioImporter/export_v1", ScenarioImporter.export_v1, name="scenario_export_v1"),
    path("SceneController/create", SceneController.create, name="scene_create"),
    path("SceneController/update", SceneController.update, name="scene_update"),
    path("SceneGeometryReader/meshes", SceneGeometryReader.meshes, name="scene_geometry_meshes"),
    path("SceneGeometryReader/bounds", SceneGeometryReader.bounds, name="scene_geometry_bounds"),
    path("SceneGeometryReader/height_map", SceneGeometryReader.height_map, name="scene_geometry_height_map"),
    path("SceneGeometryReader/coverage", SceneGeometryReader.coverage, name="scene_geometry_coverage"),
    path("SceneGeometryReader/mesh_file", SceneGeometryReader.mesh_file, name="scene_geometry_mesh_file"),
    path("SceneController/duplicate", SceneController.duplicate, name="scene_duplicate"),
    path("SceneController/delete", SceneController.delete, name="scene_delete"),
    path("SceneReader/read", SceneReader.read, name="scene_read"),
    path("SceneReader/read_full_tree", SceneReader.read_full_tree, name="scene_read_full_tree"),
    path("BuildingController/create", BuildingController.create, name="building_create"),
    path("BuildingController/update", BuildingController.update, name="building_update"),
    path("BuildingController/delete", BuildingController.delete, name="building_delete"),
    path("BuildingReader/read", BuildingReader.read, name="building_read"),
    path("MaterialController/create", MaterialController.create, name="material_create"),
    path("MaterialController/update", MaterialController.update, name="material_update"),
    path("MaterialController/delete", MaterialController.delete, name="material_delete"),
    path("MaterialReader/read", MaterialReader.read, name="material_read"),
]
