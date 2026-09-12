"""cu_up routes — E1AP + DRB observability."""
from django.urls import path

from main.apps.cu_up.actors.drb_actor import DrbActor
from main.apps.cu_up.actors.e1ap_router_actor import E1ApRouterActor

urlpatterns = [
    path("E1AP/E1ApRouter/bearer_context_setup",
         E1ApRouterActor.bearer_context_setup, name="e1_bearer_setup"),
    path("UP/Drb/list", DrbActor.list, name="drb_list"),
    path("UP/Drb/read", DrbActor.read, name="drb_read"),
]
