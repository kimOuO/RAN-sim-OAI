from django.urls import path
from main.apps.scene_layout.actors.scene_actor import SceneController, SceneReader
from main.apps.scene_layout.actors.building_actor import BuildingController, BuildingReader

urlpatterns = [
    path("SceneController/create", SceneController.create, name="scene_create"),
    path("SceneController/update", SceneController.update, name="scene_update"),
    path("SceneController/delete", SceneController.delete, name="scene_delete"),
    path("SceneReader/read", SceneReader.read, name="scene_read"),
    path("BuildingController/create", BuildingController.create, name="building_create"),
    path("BuildingController/update", BuildingController.update, name="building_update"),
    path("BuildingController/delete", BuildingController.delete, name="building_delete"),
    path("BuildingReader/read", BuildingReader.read, name="building_read"),
]
