from django.urls import path
from main.apps.simulation_run.actors.scene_run_actor import SceneRunController, SceneRunReader
from main.apps.simulation_run.actors.run_knob_actor import RunKnobController, RunKnobReader
from main.apps.simulation_run.actors.run_instance_actor import RunInstanceController, RunInstanceReader

urlpatterns = [
    path("SceneRunController/create", SceneRunController.create, name="scene_run_create"),
    path("SceneRunController/update", SceneRunController.update, name="scene_run_update"),
    path("SceneRunController/delete", SceneRunController.delete, name="scene_run_delete"),
    path("SceneRunReader/read", SceneRunReader.read, name="scene_run_read"),
    path("RunKnobController/create", RunKnobController.create, name="run_knob_create"),
    path("RunKnobController/update", RunKnobController.update, name="run_knob_update"),
    path("RunKnobController/delete", RunKnobController.delete, name="run_knob_delete"),
    path("RunKnobReader/read", RunKnobReader.read, name="run_knob_read"),
    path("RunInstanceController/create", RunInstanceController.create, name="run_instance_create"),
    path("RunInstanceController/update", RunInstanceController.update, name="run_instance_update"),
    path("RunInstanceController/delete", RunInstanceController.delete, name="run_instance_delete"),
    path("RunInstanceReader/read", RunInstanceReader.read, name="run_instance_read"),
]
