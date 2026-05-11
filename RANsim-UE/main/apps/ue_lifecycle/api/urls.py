"""URL: /api/v0.1/UE/<Component>/<Element>"""
from django.urls import path

from main.apps.ue_lifecycle.actors.lifecycle_actor import (
    LifecycleController,
    StatusController,
)
from main.apps.ue_lifecycle.actors.trajectory_actor import TrajectoryController

urlpatterns = [
    path("Status/read", StatusController.read, name="ue_status_read"),
    path("Lifecycle/sync", LifecycleController.sync, name="ue_lifecycle_sync"),
    path("Lifecycle/start", LifecycleController.start, name="ue_lifecycle_start"),
    path("Lifecycle/stop", LifecycleController.stop, name="ue_lifecycle_stop"),
    path("Trajectory/set", TrajectoryController.set, name="ue_trajectory_set"),
    path("Trajectory/clear", TrajectoryController.clear, name="ue_trajectory_clear"),
    path("Trajectory/list", TrajectoryController.list, name="ue_trajectory_list"),
]
