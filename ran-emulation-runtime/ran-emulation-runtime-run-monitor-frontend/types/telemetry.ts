/** registry / orchestrator / DU / E2Adapter 的 DTO(對齊後端 model 欄位) */
export interface SceneRun {
  scene_run_uuid: string; mode: 'live' | 'cached'; speed_x: number; sim_dt_ms: number; duration_sec: number;
  status: string; cache_path: string; e2_node_id: string; started_at: string | null; stopped_at: string | null; notes: string; f_scene_uuid: string;
}
export interface Scene { scene_uuid: string; name: string; legacy_scenario_id: string; }
export interface UeKpm {
  serving_cell: string; rsrp_dbm: number; sinr_db: number; throughput_dl_mbps: number; throughput_ul_mbps: number; mcs_dl: number;
  rb_width_dl: number; mimo_rank: number; pdcp_sdu_volume_dl: number; pdcp_sdu_volume_ul: number; rlc_sdu_delay_dl_ms: number; qos_5qi: number;
  neighbor_cells_json: unknown;
}
export interface CellKpm { prb_pct_dl: number; prb_pct_ul: number; window_seconds: number; }
export interface KpmSample { run_kpm_sample_uuid: string; f_scene_run_uuid: string; window_index: number; sim_time_ms: number; wall_time_ms: number; per_cell: Record<string, CellKpm>; per_ue: Record<string, UeKpm>; warnings: string[]; run_kpm_sample_created_at: string; }
export interface HandoverEvent { run_handover_event_uuid: string; at_sim_ms: number; ue_id: string; source_cell: string; target_cell: string; outcome: string; detail: Record<string, unknown> | null; run_handover_event_created_at: string; }
export interface ControlEvent { run_control_event_uuid: string; at_sim_ms: number; source: string; action_type: string; target: string; outcome: string; landing_latency_ms: number | null; detail: Record<string, unknown> | null; run_control_event_created_at: string; }
export interface LaunchRequest { launch_request_uuid: string; action: string; status: string; mode: string; speed_x: number; detail: unknown; launch_request_created_at: string; }
export interface DuTick { tick_count: number; is_running: boolean; wall_tick_ms: number; sim_dt_ms: number; sim_speed_x: number; achieved_speed_x: number; }
export interface E2AdapterStatus { sctp_link: { enabled: boolean; target_host: string; target_port: number; connected: boolean; last_connect_at?: string | null }; [k: string]: unknown; }
