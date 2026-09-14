from django.urls import path
from main.apps.run_lifecycle.actors.precompute_actor import PrecomputeController, PrecomputeReader, RicObservationReader
from main.apps.run_lifecycle.actors.launch_request_actor import LaunchController, LaunchRequestController, LaunchRequestReader

urlpatterns = [
    path("LaunchController/start", LaunchController.start, name="launch_start"),
    path("LaunchController/stop", LaunchController.stop, name="launch_stop"),
    path("LaunchRequestController/create", LaunchRequestController.create, name="launch_request_create"),
    path("LaunchRequestController/update", LaunchRequestController.update, name="launch_request_update"),
    path("LaunchRequestController/delete", LaunchRequestController.delete, name="launch_request_delete"),
    path("LaunchRequestReader/read", LaunchRequestReader.read, name="launch_request_read"),
    path("PrecomputeController/start", PrecomputeController.start, name="precompute_start"),
    path("PrecomputeController/stop", PrecomputeController.stop, name="precompute_stop"),
    path("PrecomputeReader/read", PrecomputeReader.read, name="precompute_read"),
    path("RicObservationReader/read", RicObservationReader.read, name="ric_observation_read"),
]
