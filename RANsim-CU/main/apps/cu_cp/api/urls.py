"""cu_cp routes — direct binding from Module/Component/Element to Actor.method."""
from django.urls import path

from main.apps.cu_cp.actors.e2_control_actor import E2ControlActor
from main.apps.cu_cp.actors.e2_kpm_reporter_actor import E2KpmReporterActor
from main.apps.cu_cp.actors.e2_node_id_actor import E2NodeIdActor
from main.apps.cu_cp.actors.e2_subscription_actor import E2IndicationActor, E2SubscriptionActor
from main.apps.cu_cp.actors.f1ap_router_actor import F1ApRouterActor
from main.apps.cu_cp.actors.log_actor import LogActor
from main.apps.cu_cp.actors.handover_event_actor import HandoverEventActor
from main.apps.cu_cp.actors.mobility_actor import MobilityActor
from main.apps.cu_cp.actors.ngap_router_actor import NgapRouterActor
from main.apps.cu_cp.actors.session_controller_actor import SessionControllerActor

urlpatterns = [
    # F1AP
    path("F1AP/F1ApRouter/du_setup", F1ApRouterActor.du_setup, name="f1_du_setup"),
    path("F1AP/F1ApRouter/du_configuration_update", F1ApRouterActor.du_configuration_update, name="f1_du_config_update"),
    path("F1AP/F1ApRouter/ul_rrc_message", F1ApRouterActor.ul_rrc_message, name="f1_ul_rrc"),
    path("F1AP/F1ApRouter/measurement_report", F1ApRouterActor.measurement_report, name="f1_meas"),
    path("F1AP/F1ApRouter/cell_measurement_report", F1ApRouterActor.cell_measurement_report, name="f1_cell_meas"),
    # NGAP
    path("NGAP/NgapRouter/initial_ue_message", NgapRouterActor.initial_ue_message, name="ngap_init_ue"),
    path("NGAP/NgapRouter/initial_context_setup", NgapRouterActor.initial_context_setup, name="ngap_init_ctx"),
    path("NGAP/NgapRouter/downlink_nas_transport", NgapRouterActor.downlink_nas_transport, name="ngap_dl_nas"),
    # Session (Dashboard)
    path("Session/SessionController/list", SessionControllerActor.list, name="session_list"),
    path("Session/SessionController/handover", SessionControllerActor.handover, name="session_ho"),
    path("Session/SessionController/get_state", SessionControllerActor.get_state, name="session_state"),
    path("Session/SessionController/release_stale", SessionControllerActor.release_stale, name="session_release_stale"),
    path("Session/SessionController/update_traffic_profile", SessionControllerActor.update_traffic_profile, name="session_update_traffic"),
    # ── E2 介面（對齊 OAI E2AP / E2-SM-KPM / E2-SM-RC）─────────────────
    # 舊的：簡單 polling snapshot（保留向後相容）
    path("E2/E2KpmReporter/read", E2KpmReporterActor.read, name="e2_kpm_read"),
    # 新的：xApp 訂閱 / poll indication / 下 control（對齊 OAI 三段式 RIC 流程）
    path("E2/Subscription/create", E2SubscriptionActor.create, name="e2_sub_create"),  # ↔ OAI RIC Subscription Request
    path("E2/Subscription/delete", E2SubscriptionActor.delete, name="e2_sub_delete"),  # ↔ OAI RIC Subscription Delete Request
    path("E2/Subscription/list",   E2SubscriptionActor.list,   name="e2_sub_list"),    # adapter 重啟恢復用
    path("E2/Indication/poll", E2IndicationActor.poll, name="e2_ind_poll"),            # ↔ OAI RIC Indication (polling 取代 SCTP push)
    path("E2/Control/request", E2ControlActor.request, name="e2_ctrl_request"),        # ↔ OAI RIC Control Request
    path("E2/E2NodeId/read", E2NodeIdActor.read, name="e2_node_id_read"),              # ↔ globalE2node-ID for E2 adapter
    # Logs（Dashboard /logs page 用）
    path("Logs/Ring/read", LogActor.read_ring, name="logs_ring_read"),
    # AK11: Mobility A3 runtime config (Dashboard 控制 A3 開關 + 參數)
    path("Mobility/A3Controller/read", MobilityActor.read_a3, name="mobility_a3_read"),
    path("Mobility/A3Controller/set",  MobilityActor.set_a3,  name="mobility_a3_set"),
    # Mobility HO event history (Dashboard HandoverMap)
    path("Mobility/HandoverEvent/list", HandoverEventActor.list, name="ho_event_list"),
]
