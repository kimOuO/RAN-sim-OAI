"""Routes for /api/v0.1/RU/Config/...

backend_rule §2-2 / §7-1：直接綁 Actor.function。
"""
from django.urls import path

from main.apps.antenna.actors.ru_controller import RuController

urlpatterns = [
    path("RuController/update_antenna", RuController.update_antenna, name="ru_update_antenna"),
    path("RuController/update_cells",   RuController.update_cells,   name="ru_update_cells"),
    path("RuController/update_ues",     RuController.update_ues,     name="ru_update_ues"),
    path("RuController/set_channel_mode", RuController.set_channel_mode, name="ru_set_channel_mode"),
    path("RuController/set_inter_freq",   RuController.set_inter_freq,   name="ru_set_inter_freq"),
]
