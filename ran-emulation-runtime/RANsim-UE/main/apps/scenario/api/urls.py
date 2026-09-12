"""URL: /api/v0.1/UE/Scenario/<Component>/<Element>"""
from django.urls import path

from main.apps.scenario.actors.scenario_controller_actor import ScenarioController


urlpatterns = [
    path("ScenarioController/start", ScenarioController.start, name="scen_start"),
    path("ScenarioController/stop", ScenarioController.stop, name="scen_stop"),
    path("ScenarioController/status", ScenarioController.status, name="scen_status"),
]
