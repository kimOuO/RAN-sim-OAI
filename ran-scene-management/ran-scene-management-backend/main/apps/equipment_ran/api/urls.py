from django.urls import path
from main.apps.equipment_ran.actors.gnb_actor import GnbController, GnbReader
from main.apps.equipment_ran.actors.du_actor import DuController, DuReader
from main.apps.equipment_ran.actors.cell_actor import CellController, CellReader
from main.apps.equipment_ran.actors.ru_actor import RuController, RuReader
from main.apps.equipment_ran.actors.neighbor_seed_actor import NeighborSeedController, NeighborSeedReader

urlpatterns = [
    path("GnbController/create", GnbController.create, name="gnb_create"),
    path("GnbController/update", GnbController.update, name="gnb_update"),
    path("GnbController/delete", GnbController.delete, name="gnb_delete"),
    path("GnbReader/read", GnbReader.read, name="gnb_read"),
    path("DuController/create", DuController.create, name="du_create"),
    path("DuController/update", DuController.update, name="du_update"),
    path("DuController/delete", DuController.delete, name="du_delete"),
    path("DuReader/read", DuReader.read, name="du_read"),
    path("CellController/create", CellController.create, name="cell_create"),
    path("CellController/update", CellController.update, name="cell_update"),
    path("CellController/delete", CellController.delete, name="cell_delete"),
    path("CellReader/read", CellReader.read, name="cell_read"),
    path("RuController/create", RuController.create, name="ru_create"),
    path("RuController/update", RuController.update, name="ru_update"),
    path("RuController/delete", RuController.delete, name="ru_delete"),
    path("RuReader/read", RuReader.read, name="ru_read"),
    path("NeighborSeedController/create", NeighborSeedController.create, name="neighbor_seed_create"),
    path("NeighborSeedController/update", NeighborSeedController.update, name="neighbor_seed_update"),
    path("NeighborSeedController/delete", NeighborSeedController.delete, name="neighbor_seed_delete"),
    path("NeighborSeedReader/read", NeighborSeedReader.read, name="neighbor_seed_read"),
]
