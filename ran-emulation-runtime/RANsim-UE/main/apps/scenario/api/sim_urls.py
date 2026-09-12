"""URL: /api/v0.1/UE/Sim/<Component>/<Element>"""
from django.urls import path

from main.apps.scenario.actors.sim_controller_actor import SimController


urlpatterns = [
    path("SimController/start", SimController.start, name="sim_start"),
    path("SimController/stop", SimController.stop, name="sim_stop"),
]
