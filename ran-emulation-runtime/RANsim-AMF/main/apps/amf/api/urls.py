"""URL: /api/v0.1/AMF/<Module>/<Component>/<Element>"""
from django.urls import path

from main.apps.amf.actors.amf_router_actor import AmfRouterActor, StatusActor

urlpatterns = [
    path("Ngap/AmfRouter/ng_setup", AmfRouterActor.ng_setup, name="amf_ng_setup"),
    path("Ngap/AmfRouter/initial_ue_message", AmfRouterActor.initial_ue_message, name="amf_initial_ue_message"),
    path("Ngap/AmfRouter/path_switch_request", AmfRouterActor.path_switch_request, name="amf_path_switch_request"),
    path("Ngap/AmfRouter/handover_required", AmfRouterActor.handover_required, name="amf_handover_required"),
    path("Ngap/AmfRouter/handover_notify", AmfRouterActor.handover_notify, name="amf_handover_notify"),
    path("Ngap/AmfRouter/ue_context_release", AmfRouterActor.ue_context_release, name="amf_ue_context_release"),
    path("Status/read", StatusActor.read, name="amf_status_read"),
    path("Status/ues", StatusActor.ues, name="amf_status_ues"),
]
