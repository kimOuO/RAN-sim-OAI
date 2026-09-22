"""Routes for /api/v0.1/RU/Config/...

backend_rule §2-2 / §7-1：直接綁 Actor.function。
"""
from django.urls import path

from main.apps.antenna.actors.ru_controller import BeamController, RuController

urlpatterns = [
    path("RuController/update_antenna", RuController.update_antenna, name="ru_update_antenna"),
    path("RuController/update_cells",   RuController.update_cells,   name="ru_update_cells"),
    path("RuController/set_cell_power", RuController.set_cell_power, name="ru_set_cell_power"),
    path("RuController/set_cell_antenna", RuController.set_cell_antenna, name="ru_set_cell_antenna"),
    path("RuController/update_ues",     RuController.update_ues,     name="ru_update_ues"),
    path("RuController/set_channel_mode", RuController.set_channel_mode, name="ru_set_channel_mode"),
    path("BeamController/set",  BeamController.set,  name="ru_beam_control_set"),
    path("BeamController/read", BeamController.read, name="ru_beam_control_read"),
    path("RuController/set_inter_freq",   RuController.set_inter_freq,   name="ru_set_inter_freq"),
]
