from django.urls import path
from main.apps.run_lifecycle.actors.launch_request_actor import LaunchRequestController, LaunchRequestReader

urlpatterns = [
    path("LaunchRequestController/create", LaunchRequestController.create, name="launch_request_create"),
    path("LaunchRequestController/update", LaunchRequestController.update, name="launch_request_update"),
    path("LaunchRequestController/delete", LaunchRequestController.delete, name="launch_request_delete"),
    path("LaunchRequestReader/read", LaunchRequestReader.read, name="launch_request_read"),
]
