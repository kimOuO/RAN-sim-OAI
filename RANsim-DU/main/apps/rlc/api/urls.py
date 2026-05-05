"""URL: /api/v0.1/DU/RLC/<Component>/<Element>"""
from django.urls import path

from main.apps.rlc.actors.rlc_data_actor import RlcDataController
from main.apps.rlc.actors.rlc_entity_actor import RlcEntityController

urlpatterns = [
    path("RlcEntityController/create", RlcEntityController.create, name="rlc_entity_create"),
    path("RlcEntityController/read", RlcEntityController.read, name="rlc_entity_read"),
    path("RlcEntityController/delete", RlcEntityController.delete, name="rlc_entity_delete"),
    path("RlcDataController/inject_sdu", RlcDataController.inject_sdu, name="rlc_data_inject_sdu"),
    path(
        "RlcDataController/read_buffer_status",
        RlcDataController.read_buffer_status,
        name="rlc_data_buffer_status",
    ),
]
