"""cu_cp routes — direct binding from Module/Component/Element to Actor.method."""
from django.urls import path

from main.apps.cu_cp.actors.e2_control_actor import E2ControlActor
from main.apps.cu_cp.actors.e2_full_reporter_actor import E2FullReporterActor
from main.apps.cu_cp.actors.e2_kpm_reporter_actor import E2KpmReporterActor
from main.apps.cu_cp.actors.e2_kpm_speed_actor import E2KpmSpeedActor
from main.apps.cu_cp.actors.e2_node_id_actor import E2NodeIdActor
from main.apps.cu_cp.actors.anr_control_actor import AnrControlActor
from main.apps.cu_cp.actors.anr_query_actor import AnrQueryActor
from main.apps.cu_cp.actors.e2_subscription_actor import E2IndicationActor, E2SubscriptionActor
from main.apps.cu_cp.actors.f1ap_router_actor import F1ApRouterActor
from main.apps.cu_cp.actors.log_actor import LogActor
from main.apps.cu_cp.actors.handover_event_actor import HandoverEventActor
from main.apps.cu_cp.actors.anr_query_actor import AnrFixtureActor
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
    path("F1AP/F1ApRouter/rlf_report", F1ApRouterActor.rlf_report, name="f1_rlf_report"),  # P1-1/2 RLF + 重建
    # NGAP
    path("NGAP/NgapRouter/initial_ue_message", NgapRouterActor.initial_ue_message, name="ngap_init_ue"),
    path("NGAP/NgapRouter/initial_context_setup", NgapRouterActor.initial_context_setup, name="ngap_init_ctx"),
    path("NGAP/NgapRouter/downlink_nas_transport", NgapRouterActor.downlink_nas_transport, name="ngap_dl_nas"),
    # Session (Dashboard)
    path("Session/SessionController/list", SessionControllerActor.list, name="session_list"),
    path("Session/SessionController/handover", SessionControllerActor.handover, name="session_ho"),
    path("Session/SessionController/get_state", SessionControllerActor.get_state, name="session_state"),
    path("Session/SessionController/release_stale", SessionControllerActor.release_stale, name="session_release_stale"),
    path("Session/SessionController/release_all", SessionControllerActor.release_all, name="session_release_all"),
    path("Session/SessionController/update_traffic_profile", SessionControllerActor.update_traffic_profile, name="session_update_traffic"),
    # ── E2 介面（對齊 OAI E2AP / E2-SM-KPM / E2-SM-RC）─────────────────
    # 舊的：簡單 polling snapshot（保留向後相容）
    path("E2/E2KpmReporter/read", E2KpmReporterActor.read, name="e2_kpm_read"),
    # 完整版:欄位架構 1:1 對齊 docs/E2_data_example.md(e2/ue_status/pm/bbu_status)
    path("E2/E2FullReporter/read", E2FullReporterActor.read, name="e2_full_kpm_read"),
    # 新的：xApp 訂閱 / poll indication / 下 control（對齊 OAI 三段式 RIC 流程）
    path("E2/Subscription/create", E2SubscriptionActor.create, name="e2_sub_create"),  # ↔ OAI RIC Subscription Request
    path("E2/Subscription/delete", E2SubscriptionActor.delete, name="e2_sub_delete"),  # ↔ OAI RIC Subscription Delete Request
    path("E2/Subscription/list",   E2SubscriptionActor.list,   name="e2_sub_list"),    # adapter 重啟恢復用
    path("E2/Indication/poll", E2IndicationActor.poll, name="e2_ind_poll"),            # ↔ OAI RIC Indication (polling 取代 SCTP push)
    path("E2/Control/request", E2ControlActor.request, name="e2_ctrl_request"),        # ↔ OAI RIC Control Request
    path("E2/CellEsState/read", E2ControlActor.cell_es_state, name="e2_cell_es_state"), # cell energySavingState(給 CCC indication producer)
    path("E2/E2NodeId/read", E2NodeIdActor.read, name="e2_node_id_read"),              # ↔ globalE2node-ID for E2 adapter
    # ── ANR / E2 Node Information（E2SM-ANR M0：鄰區關係表觀測）─────────────
    path("E2/NodeInfo/read", AnrQueryActor.node_info, name="e2_nodeinfo_read"),        # ↔ RC_E2NODEINFO_QUERY(§9.3.38)
    path("E2/Anr/set_barred", AnrQueryActor.set_barred, name="e2_anr_set_barred"),   # TS 38.331 cellBarred
    path("E2/Anr/reseed", AnrQueryActor.reseed, name="e2_anr_reseed"),                 # 手動重種 NRT + CGI
    # P0-2/3/4(2026-08-11):ANR KPM 查詢層(對齊 ANR情境_v8 卷面資料塊)
    path("E2/Anr/kpm", AnrQueryActor.kpm, name="e2_anr_kpm"),                          # HO 速率/成功比(cell+關係級)
    path("E2/Anr/meas_aggregate", AnrQueryActor.meas_aggregate, name="e2_anr_meas_agg"),  # 量測聚合(依 PCI)
    path("E2/Anr/cgi_resolve", AnrQueryActor.cgi_resolve, name="e2_anr_cgi_resolve"),  # PCI→NCGI(confusion 感知)
    path("E2/Anr/rlf_kpm", AnrQueryActor.rlf_kpm, name="e2_anr_rlf_kpm"),              # P1-3 RLF/重建速率 + inbound-by-prevPci
    path("E2/Anr/mro_kpm", AnrQueryActor.mro_kpm, name="e2_anr_mro_kpm"),              # P2-1 MRO 歸因三聯速率
    path("E2/Anr/indication", AnrQueryActor.indication, name="e2_anr_indication"),
    # 永遠回 v10(不受 ANR_SCHEMA 影響)—— 給 RIC 遷移期間開發用,不必等切換
    path("E2/Anr/indication_v10", AnrQueryActor.indication_v10, name="e2_anr_indication_v10"),    # ran_func 6 producer 資料源(卷面全塊)
    path("E2/Anr/control", AnrControlActor.control, name="e2_anr_control"),            # ↔ SONTRIG_ANR_ADD/REMOVE/FLAG
    # KPM sim-speed knob — Dashboard 切 DU tick 速度時同步通知,讓 indication producer
    # 用 sim-time 為單位算 report_period_ms,不是 wall-clock。
    path("E2/KpmSpeed/set",  E2KpmSpeedActor.set,  name="e2_kpm_speed_set"),
    path("E2/KpmSpeed/read", E2KpmSpeedActor.read, name="e2_kpm_speed_read"),
    # Logs（Dashboard /logs page 用）
    path("Logs/Ring/read", LogActor.read_ring, name="logs_ring_read"),
    # AK11: Mobility A3 runtime config (Dashboard 控制 A3 開關 + 參數)
    # 劇本病徵時間軸:場景套用後由 scenario_driver 觸發,不再需要人手動起
    path("Anr/Fixture/start", AnrFixtureActor.start, name="anr_fixture_start"),
    path("Mobility/A3Controller/read", MobilityActor.read_a3, name="mobility_a3_read"),
    path("Mobility/A3Controller/set",  MobilityActor.set_a3,  name="mobility_a3_set"),
    # Mobility HO event history (Dashboard HandoverMap)
    path("Mobility/HandoverEvent/list", HandoverEventActor.list, name="ho_event_list"),
]
