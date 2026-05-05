"""cu_cp routes — direct binding from Module/Component/Element to Actor.method."""
from django.urls import path

from main.apps.cu_cp.actors.e2_kpm_reporter_actor import E2KpmReporterActor
from main.apps.cu_cp.actors.f1ap_router_actor import F1ApRouterActor
from main.apps.cu_cp.actors.ngap_router_actor import NgapRouterActor
from main.apps.cu_cp.actors.session_controller_actor import SessionControllerActor

urlpatterns = [
    # F1AP
    path("F1AP/F1ApRouter/du_setup", F1ApRouterActor.du_setup, name="f1_du_setup"),
    path("F1AP/F1ApRouter/ul_rrc_message", F1ApRouterActor.ul_rrc_message, name="f1_ul_rrc"),
    path("F1AP/F1ApRouter/measurement_report", F1ApRouterActor.measurement_report, name="f1_meas"),
    # NGAP
    path("NGAP/NgapRouter/initial_ue_message", NgapRouterActor.initial_ue_message, name="ngap_init_ue"),
    path("NGAP/NgapRouter/initial_context_setup", NgapRouterActor.initial_context_setup, name="ngap_init_ctx"),
    path("NGAP/NgapRouter/downlink_nas_transport", NgapRouterActor.downlink_nas_transport, name="ngap_dl_nas"),
    # Session (Dashboard)
    path("Session/SessionController/list", SessionControllerActor.list, name="session_list"),
    path("Session/SessionController/handover", SessionControllerActor.handover, name="session_ho"),
    path("Session/SessionController/get_state", SessionControllerActor.get_state, name="session_state"),
    # E2 KPM (xApp / RIC)
    path("E2/E2KpmReporter/read", E2KpmReporterActor.read, name="e2_kpm_read"),
]
