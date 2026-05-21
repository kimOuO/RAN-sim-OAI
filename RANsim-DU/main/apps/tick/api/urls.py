"""URL: /api/v0.1/DU/Tick/<Component>/<Element>"""
from django.urls import path

from main.apps.tick.actors.tick_controller_actor import TickController

urlpatterns = [
    path("TickController/start", TickController.start, name="tick_start"),
    path("TickController/stop", TickController.stop, name="tick_stop"),
    path("TickController/run_once", TickController.run_once, name="tick_run_once"),
    path("TickController/read", TickController.read, name="tick_read"),
    path("TickController/set_speed", TickController.set_speed, name="tick_set_speed"),
    path("TickController/dump_pm", TickController.dump_pm, name="tick_dump_pm"),
    path("TickController/register_ue", TickController.register_ue, name="tick_register_ue"),
    path("TickController/replace_ues", TickController.replace_ues, name="tick_replace_ues"),
]
