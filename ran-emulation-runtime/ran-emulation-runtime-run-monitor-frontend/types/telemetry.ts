/** registry / orchestrator / DU / UE / E2Adapter 的 DTO(對齊後端欄位) */
export interface SceneRun {
  scene_run_uuid: string; mode: 'live' | 'cached'; speed_x: number; sim_dt_ms: number; duration_sec: number;
  /** 2026-09-28:idle / precomputing / running;上一次結果另存 last_result */
  status: string; last_result?: string; cache_path: string; e2_node_id: string; started_at: string | null; stopped_at: string | null; notes: string; f_scene_uuid: string;
}
export interface Scene { scene_uuid: string; name: string; legacy_scenario_id: string; category?: string; description?: string; }
/** registry read_full_tree 的子集:只要 gNB → cell 名稱對應 */
export interface SceneTreeLite { scene: Scene; gnbs: { gnb_uuid: string; name: string; dus: { name?: string; cells: { cell_uuid: string; name: string; pci: number }[] }[] }[]; }
export interface UeKpm {
  /** Live view may overlay the UE driver's actual RRC connection state. */
  attached?: boolean;
  serving_cell: string; rsrp_dbm: number; sinr_db: number; throughput_dl_mbps: number; throughput_ul_mbps: number; mcs_dl: number;
  rb_width_dl: number; mimo_rank: number; pdcp_sdu_volume_dl: number; pdcp_sdu_volume_ul: number; rlc_sdu_delay_dl_ms: number; qos_5qi: number;
  neighbor_cells_json: { cell_id: string; rsrp_dbm: number; rsrq_db: number }[] | null;
  /** P6 / P5-4 上行與每層(舊樣本可能缺) */
  mcs_ul?: number; rb_width_ul?: number; ul_sinr_db?: number | null; sinr_layers_json?: number[] | null;
  /** B1:O-RAN Cat B 的 GoB 波束 id(predefined-beam);null = 這個 cell 沒有波束網格 */
  beam_id?: number | null;
}
/** 回放清單的一列:某個 run 的某一次執行 */
export interface RunExecution { f_scene_run_uuid: string; run_seq: number; ric_run: number; started_ms: number | null; ended_ms: number | null; wall_sec: number; sim_start_sec: number | null; sim_end_sec: number | null; sim_sec: number | null; windows: number; ue_count: number; cell_count: number; handovers: number; handover_succ: number; rlf: number; controls: number; }
export interface CellKpm { prb_pct_dl: number; prb_pct_ul: number; window_seconds: number; }
export interface KpmSample { id: number; run_kpm_sample_uuid: string; f_scene_run_uuid: string; window_index: number; sim_time_ms: number; scene_t_sec?: number | null; wall_time_ms: number; per_cell: Record<string, CellKpm>; per_ue: Record<string, UeKpm>; warnings: string[]; run_kpm_sample_created_at: string; }
export interface HandoverEvent { id: number; run_handover_event_uuid: string; at_sim_ms: number; ue_id: string; source_cell: string; target_cell: string; outcome: string; detail: Record<string, unknown> | null; run_handover_event_created_at: string; }
export interface ControlEvent { run_control_event_uuid: string; at_sim_ms: number; source: string; action_type: string; target: string; outcome: string; landing_latency_ms: number | null; detail: Record<string, unknown> | null; run_control_event_created_at: string; meid?: string | null; node_id?: string | null; ric_run?: number | null; }
export interface LaunchRequest { launch_request_uuid: string; action: string; status: string; mode: string; speed_x: number; detail: unknown; launch_request_created_at: string; }
export interface DuTick { tick_count: number; sfn: number; slot: number; is_running: boolean; wall_tick_ms: number; sim_dt_ms: number; sim_speed_x: number; achieved_speed_x: number; }
export interface DuCell { cell_id: string; pci: number; total_prb: number; freq_ghz: number; bw_mhz: number; gnb_id: string; is_active: boolean; }
export interface UeDriverStatus { running: boolean; scenario_id: string; phase: string; ue_count: number; traffic_count: number; sim_speed_x: number; total_ticks: number; sim_tick_idx: number; elapsed_wall_sec: number; elapsed_sim_sec: number; attach_failed: string[]; scene_apply_errors: string[]; started_at_ms?: number; clock_running?: boolean; achieved_speed_x?: number; duration_sec?: number; attached_count?: number; }
/** CU 收到並接受的 E2 訂閱(RIC 視角的「哪個 xApp 要了什麼」) */
export interface E2Subscription { subscription_id: string; service_model: string; ran_function_id: number; ric_req_id: { instance_id: number; requestor_id: number }; action_definition?: { metrics?: string[]; report_period_ms?: number } & Record<string, unknown>; event_trigger?: { report_period_ms?: number } & Record<string, unknown>; created_at_ms: number; producer?: string; }
export interface E2AdapterStatus { sctp_link: { enabled: boolean; target_host: string; target_port: number; connected: boolean; last_error?: string }; [k: string]: unknown; }

/** 圖表用的序列 */
export interface Pt { x: number; y: number | null; }
export interface Series { key: string; label: string; color: string; points: Pt[]; }
/** RIC 閘道視角:這個 run 被哪個 xApp pod 觀測(orchestrator RicObservationReader) */
export interface RicObservedBy { name: string; phase: string; ready: boolean; podIP?: string; }
export interface RicNode { meid: string; e2ConnectionStatus?: string; subscriptionCount?: number | null; degraded?: string[]; view?: { xappName?: string; observedBy?: RicObservedBy[]; state?: string } | null; }
export interface RicObservation { scene_run_uuid: string; gateway: boolean; scenario: { xappName?: string; profile?: string; isolation?: string; state?: string; ranFunctions?: number[]; connectedNodes?: number; controlPolicy?: { allowedStyles?: string[]; allowWrite?: boolean }; error?: string } | null; nodes: Record<string, RicNode>; }
/** 多 gNB(2026-09-27):同一角色可有多個實例(cu / du / e2adapter 每個 gNB / DU 一個);name 是容器名,e2_node_id 是所屬 E2 node */
export interface RunInstance { run_instance_uuid: string; role: 'amf' | 'cu' | 'du' | 'ru' | 'ue' | 'e2adapter'; name?: string; gnb_uuid?: string | null; du_uuid?: string | null; e2_node_id?: string; container_id: string; host_port: number | null; status: string; last_heartbeat: string | null; health_detail?: string; f_scene_run_uuid: string; }
/** 3D 畫面用的完整場景樹(read_full_tree):位置 Y-up、公尺;UE 路徑點 [t, x, y, z] */
/** 天線範本的外觀相關欄位(3D 依此畫全向 / 扇區 / mMIMO) */
export interface AntennaPresetLite { name?: string; pattern: string; rows: number; cols: number; }
export interface Cell3d { cell_uuid: string; name: string; pci: number; position: number[] | null; azimuth_deg: number; tilt_deg: number; is_active: boolean; ru?: { antenna_preset?: AntennaPresetLite | null } | null; }
export interface Gnb3d { gnb_uuid: string; name: string; position: number[]; dus: { name?: string; cells: Cell3d[] }[]; }
export interface Ue3d { ue_uuid: string; name: string; waypoints: [number, number, number, number][]; active_windows: [number, number][]; presence_restricted?: boolean; }
export interface Building3d { building_uuid: string; name: string; position: number[]; size: number[]; }
export interface SceneTree3d { scene: Scene & { geometry_source: unknown; gnb_antenna_preset?: AntennaPresetLite | null }; gnbs: Gnb3d[]; ues: Ue3d[]; buildings: Building3d[]; }
