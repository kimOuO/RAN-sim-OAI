"""URL: /api/v0.1/DU/MAC/<Component>/<Element>"""
from django.urls import path

from main.apps.mac.actors.cell_actor import MacCellController
from main.apps.mac.actors.harq_actor import MacHarqController
from main.apps.mac.actors.ue_state_actor import MacUeStateController

urlpatterns = [
    path("MacCellController/create", MacCellController.create, name="mac_cell_create"),
    path("MacCellController/read", MacCellController.read, name="mac_cell_read"),
    path("MacCellController/update", MacCellController.update, name="mac_cell_update"),
    path("MacUeStateController/read", MacUeStateController.read, name="mac_ue_read"),
    path("MacHarqController/read", MacHarqController.read, name="mac_harq_read"),
]
