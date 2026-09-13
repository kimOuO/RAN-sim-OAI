/** registry(network-element-registry)的 DTO。欄位名對齊後端 model;FK 一律 f_<parent>_uuid。 */
export interface Material { material_uuid: string; key: string; itu_id: string; freq_range_ghz: string; notes: string; }
export interface AntennaPreset {
  antenna_preset_uuid: string; name: string; source: string; pattern: 'iso' | 'dipole' | 'hw_dipole' | 'tr38901';
  rows: number; cols: number; polarization: 'V' | 'H' | 'VH' | 'cross'; v_spacing: number; h_spacing: number;
  polarization_model: string; max_gain_dbi: number; notes: string;
}
export interface DuConfigTemplate {
  du_config_template_uuid: string; name: string; tdd_pattern: string; numerology: number; n_prb: number; min_prb: number;
  pf_alpha: number; target_bler: number; rlc_discard_timer_ms: number; rlc_tx_maxsize_bytes: number; harq_max_retx: number;
  qos_gbr_first: boolean; gbr_max_share: number;
}
export interface Scene {
  scene_uuid: string; name: string; description: string; origin_lat: number | null; origin_lon: number | null; bounds: unknown;
  legacy_scenario_id: string; geometry_scene_id: string; geometry_source: unknown; f_material_uuid: string | null;
  scene_created_at: string; scene_updated_at: string;
}
export interface Building {
  building_uuid: string; name: string; source: 'glb_scan' | 'osm' | 'manual_box'; geometry_ref: string;
  position: number[]; rotation: number[]; scale: number[]; size: number[]; materials_npz: string;
  f_scene_uuid: string; f_material_uuid: string | null; default_material?: Material | null;
}
export interface Ru { ru_uuid: string; name: string; antenna_override: unknown; noise_figure_db: number; f_cell_uuid: string; f_antenna_preset_uuid: string | null; antenna_preset?: AntennaPreset | null; }
export interface Cell {
  cell_uuid: string; name: string; pci: number; nr_cellid: number | null; arfcn: number | null; center_frequency_ghz: number | null;
  band: string; bandwidth_mhz: number; position: number[] | null; azimuth_deg: number; tilt_deg: number; power_dbm: number;
  is_active: boolean; is_barred: boolean; f_du_uuid: string; ru?: Ru | null;
}
export interface Du { du_uuid: string; name: string; gnb_du_id: number; config_override: unknown; f_gnb_uuid: string; f_du_config_template_uuid: string | null; config_template?: DuConfigTemplate | null; cells: Cell[]; }
export interface Gnb {
  gnb_uuid: string; name: string; gnb_id: number; plmn_mcc: string; plmn_mnc: string; position: number[]; is_active: boolean; color: number[] | null;
  a3_enabled: boolean | null; a3_offset_db: number | null; a3_hys_db: number | null; a3_ttt_ms: number | null; f_scene_uuid: string; dus: Du[];
}
export interface UeTraffic { ue_traffic_uuid: string; pattern: string; rate_mbps: number; schedule: number[][] | null; bearer_id: number; }
export interface Ue {
  ue_uuid: string; name: string; antenna_height_m: number; qos_5qi: number; color: number[]; loop: boolean; speed_mps: number | null;
  f_scene_uuid: string; f_antenna_preset_uuid: string | null; antenna_preset?: AntennaPreset | null;
  waypoints: [number, number, number, number][]; traffic: UeTraffic[]; active_windows: [number, number][];
}
export interface SceneRun {
  scene_run_uuid: string; mode: 'live' | 'cached'; speed_x: number; sim_dt_ms: number; duration_sec: number;
  status: 'draft' | 'pending' | 'precomputing' | 'ready' | 'running' | 'stopped' | 'failed'; cache_path: string; e2_node_id: string;
  started_at: string | null; stopped_at: string | null; notes: string; f_scene_uuid: string; knobs?: Record<string, unknown>;
}
export interface SceneTree { scene: Scene & { ground_material?: Material }; buildings: Building[]; gnbs: Gnb[]; neighbor_seeds: unknown[]; ues: Ue[]; run: SceneRun | null; }
export interface RunKnob { run_knob_uuid: string; key: string; value: unknown; f_scene_run_uuid: string; }
