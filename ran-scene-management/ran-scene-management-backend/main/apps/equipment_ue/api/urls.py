from django.urls import path
from main.apps.equipment_ue.actors.ue_actor import UeController, UeReader
from main.apps.equipment_ue.actors.ue_waypoint_actor import UeWaypointController, UeWaypointReader
from main.apps.equipment_ue.actors.ue_traffic_actor import UeTrafficController, UeTrafficReader
from main.apps.equipment_ue.actors.ue_active_window_actor import UeActiveWindowController, UeActiveWindowReader

urlpatterns = [
    path("UeController/create", UeController.create, name="ue_create"),
    path("UeController/update", UeController.update, name="ue_update"),
    path("UeController/delete", UeController.delete, name="ue_delete"),
    path("UeReader/read", UeReader.read, name="ue_read"),
    path("UeWaypointController/create", UeWaypointController.create, name="ue_waypoint_create"),
    path("UeWaypointController/replace", UeWaypointController.replace, name="ue_waypoint_replace"),
    path("UeWaypointController/update", UeWaypointController.update, name="ue_waypoint_update"),
    path("UeWaypointController/delete", UeWaypointController.delete, name="ue_waypoint_delete"),
    path("UeWaypointReader/read", UeWaypointReader.read, name="ue_waypoint_read"),
    path("UeTrafficController/create", UeTrafficController.create, name="ue_traffic_create"),
    path("UeTrafficController/update", UeTrafficController.update, name="ue_traffic_update"),
    path("UeTrafficController/delete", UeTrafficController.delete, name="ue_traffic_delete"),
    path("UeTrafficReader/read", UeTrafficReader.read, name="ue_traffic_read"),
    path("UeActiveWindowController/create", UeActiveWindowController.create, name="ue_active_window_create"),
    path("UeActiveWindowController/update", UeActiveWindowController.update, name="ue_active_window_update"),
    path("UeActiveWindowController/delete", UeActiveWindowController.delete, name="ue_active_window_delete"),
    path("UeActiveWindowReader/read", UeActiveWindowReader.read, name="ue_active_window_read"),
]
