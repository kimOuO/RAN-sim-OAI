/** registry / orchestrator / DU / UE / E2Adapter 的 DTO(對齊後端欄位) */
export interface SceneRun {
  scene_run_uuid: string; mode: 'live' | 'cached'; speed_x: number; sim_dt_ms: number; duration_sec: number;
  status: string; cache_path: string; e2_node_id: string; started_at: string | null; stopped_at: string | null; notes: string; f_scene_uuid: string;
}
export interface Scene { scene_uuid: string; name: string; legacy_scenario_id: string; }
/** registry read_full_tree 的子集:只要 gNB → cell 名稱對應 */
export interface SceneTreeLite { scene: Scene; gnbs: { gnb_uuid: string; name: string; dus: { cells: { cell_uuid: string; name: string; pci: number }[] }[] }[]; }
export interface UeKpm {
  serving_cell: string; rsrp_dbm: number; sinr_db: number; throughput_dl_mbps: number; throughput_ul_mbps: number; mcs_dl: number;
  rb_width_dl: number; mimo_rank: number; pdcp_sdu_volume_dl: number; pdcp_sdu_volume_ul: number; rlc_sdu_delay_dl_ms: number; qos_5qi: number;
  neighbor_cells_json: { cell_id: string; rsrp_dbm: number; rsrq_db: number }[] | null;
  /** P6 / P5-4 上行與每層(舊樣本可能缺) */
  mcs_ul?: number; rb_width_ul?: number; ul_sinr_db?: number | null; sinr_layers_json?: number[] | null;
  /** B1:O-RAN Cat B 的 GoB 波束 id(predefined-beam);null = 這個 cell 沒有波束網格 */
  beam_id?: number | null;
}
export interface CellKpm { prb_pct_dl: number; prb_pct_ul: number; window_seconds: number; }
export interface KpmSample { run_kpm_sample_uuid: string; f_scene_run_uuid: string; window_index: number; sim_time_ms: number; wall_time_ms: number; per_cell: Record<string, CellKpm>; per_ue: Record<string, UeKpm>; warnings: string[]; run_kpm_sample_created_at: string; }
export interface HandoverEvent { run_handover_event_uuid: string; at_sim_ms: number; ue_id: string; source_cell: string; target_cell: string; outcome: string; detail: Record<string, unknown> | null; run_handover_event_created_at: string; }
export interface ControlEvent { run_control_event_uuid: string; at_sim_ms: number; source: string; action_type: string; target: string; outcome: string; landing_latency_ms: number | null; detail: Record<string, unknown> | null; run_control_event_created_at: string; }
export interface LaunchRequest { launch_request_uuid: string; action: string; status: string; mode: string; speed_x: number; detail: unknown; launch_request_created_at: string; }
export interface DuTick { tick_count: number; sfn: number; slot: number; is_running: boolean; wall_tick_ms: number; sim_dt_ms: number; sim_speed_x: number; achieved_speed_x: number; }
export interface DuCell { cell_id: string; pci: number; total_prb: number; freq_ghz: number; bw_mhz: number; gnb_id: string; is_active: boolean; }
export interface UeDriverStatus { running: boolean; scenario_id: string; phase: string; ue_count: number; traffic_count: number; sim_speed_x: number; total_ticks: number; sim_tick_idx: number; elapsed_wall_sec: number; elapsed_sim_sec: number; attach_failed: string[]; scene_apply_errors: string[]; }
export interface E2AdapterStatus { sctp_link: { enabled: boolean; target_host: string; target_port: number; connected: boolean; last_error?: string }; [k: string]: unknown; }

/** 圖表用的序列 */
export interface Pt { x: number; y: number | null; }
export interface Series { key: string; label: string; color: string; points: Pt[]; }
/** RIC 閘道視角:這個 run 被哪個 xApp pod 觀測(orchestrator RicObservationReader) */
export interface RicObservedBy { name: string; phase: string; ready: boolean; podIP?: string; }
export interface RicNode { meid: string; e2ConnectionStatus?: string; subscriptionCount?: number | null; degraded?: string[]; view?: { xappName?: string; observedBy?: RicObservedBy[]; state?: string } | null; }
export interface RicObservation { scene_run_uuid: string; gateway: boolean; scenario: { xappName?: string; profile?: string; isolation?: string; state?: string; ranFunctions?: number[]; connectedNodes?: number; controlPolicy?: { allowedStyles?: string[]; allowWrite?: boolean }; error?: string } | null; nodes: Record<string, RicNode>; }
export interface RunInstance { run_instance_uuid: string; role: 'cu' | 'du' | 'ru' | 'ue' | 'e2adapter'; container_id: string; host_port: number | null; status: string; last_heartbeat: string | null; health_detail?: string; f_scene_run_uuid: string; }
/** 3D 畫面用的完整場景樹(read_full_tree):位置 Y-up、公尺;UE 路徑點 [t, x, y, z] */
export interface Cell3d { cell_uuid: string; name: string; pci: number; position: number[] | null; azimuth_deg: number; tilt_deg: number; is_active: boolean; }
export interface Gnb3d { gnb_uuid: string; name: string; position: number[]; dus: { cells: Cell3d[] }[]; }
export interface Ue3d { ue_uuid: string; name: string; waypoints: [number, number, number, number][]; active_windows: [number, number][]; }
export interface Building3d { building_uuid: string; name: string; position: number[]; size: number[]; }
export interface SceneTree3d { scene: Scene & { geometry_source: unknown }; gnbs: Gnb3d[]; ues: Ue3d[]; buildings: Building3d[]; }
