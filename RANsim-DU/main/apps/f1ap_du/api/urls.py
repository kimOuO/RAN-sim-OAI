"""URL: /api/v0.1/DU/F1AP/<Component>/<Element>"""
from django.urls import path

from main.apps.f1ap_du.actors.f1_session_actor import F1SessionController
from main.apps.f1ap_du.actors.f1ap_router_actor import F1ApRouterController

urlpatterns = [
    path("F1ApRouter/ue_context_setup", F1ApRouterController.ue_context_setup, name="f1ap_ue_setup"),
    path("F1ApRouter/ue_context_modification", F1ApRouterController.ue_context_modification, name="f1ap_ue_mod"),
    path("F1ApRouter/ue_context_release", F1ApRouterController.ue_context_release, name="f1ap_ue_release"),
    path("F1ApRouter/dl_rrc_message", F1ApRouterController.dl_rrc_message, name="f1ap_dl_rrc"),
    path("F1ApRouter/ul_rrc_message", F1ApRouterController.ul_rrc_message, name="f1ap_ul_rrc"),
    path(
        "F1ApRouter/f1_setup_response",
        F1ApRouterController.f1_setup_response_callback,
        name="f1ap_setup_response",
    ),
    path("F1SessionController/read", F1SessionController.read, name="f1ap_session_read"),
]
