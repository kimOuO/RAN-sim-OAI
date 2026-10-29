/** 管理平台後端(scene-management-backend)的 DTO。欄位名對齊後端 model;FK 一律 f_<parent>_uuid。 */
export interface Material { material_uuid: string; key: string; itu_id: string; freq_range_ghz: string; notes: string; }
export interface AntennaPreset {
  antenna_preset_uuid: string; name: string; source: string; pattern: 'iso' | 'dipole' | 'hw_dipole' | 'tr38901';
  /** 元件層:單面板元件排列 M(列)× N(行),TR 38.901 §7.3 */
  rows: number; cols: number; polarization: 'V' | 'H' | 'VH' | 'cross'; v_spacing: number; h_spacing: number;
  panels_mg: number; panels_ng: number; panel_v_spacing: number; panel_h_spacing: number;
  /** TRX 層:每個 TXRU 垂直帶幾片同極化元件、TXRU 總數、電子下傾(TR 38.901 式 7.3-1) */
  trx_v_group: number; trx_count: number; electrical_tilt_deg: number;
  /** 埠層:CSI-RS 埠數與 TS 38.214 Type I 的 (N1,N2) */
  csi_ports: number; port_n1: number; port_n2: number;
  /** O-RAN WG4 CUS-plane:A = precoding 在 O-DU,B = O-RU 自己做 beamforming */
  ru_category: 'A' | 'B'; bf_method: string; gob_az_beams: number; gob_el_beams: number;
  polarization_model: string; max_gain_dbi: number; notes: string;
}
export interface DuConfigTemplate {
  du_config_template_uuid: string; name: string; tdd_pattern: string; numerology: number; n_prb: number; min_prb: number;
  pf_alpha: number; target_bler: number; rlc_discard_timer_ms: number; rlc_tx_maxsize_bytes: number; harq_max_retx: number;
  qos_gbr_first: boolean; gbr_max_share: number; scheduler: 'pf' | 'rr' | 'max_thp';
}
export interface Scene {
  scene_uuid: string; name: string; description: string; origin_lat: number | null; origin_lon: number | null; bounds: unknown;
  legacy_scenario_id: string; geometry_scene_id: string; geometry_source: unknown; f_material_uuid: string | null;
  f_gnb_antenna_preset_uuid: string | null; f_ue_antenna_preset_uuid: string | null;
  /** 釘住的 E2 區塊(1–15)。第 i 個 gNB(Gnb.e2_index)的槽位 = 16·區塊 + i,
   *  每個 gNB 一個 E2 node。釘了之後每個 gNB 的 meid 與 cell NCI 每次啟動都一樣,
   *  外部 Agent 才能事先寫進 xApp 的訂閱設定。null = 啟動時動態配。 */
  e2_block: number | null;
  category: string | null;   // 場景分類;null = 未宣告,退回名字前綴規則
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
  gnb_uuid: string; name: string; gnb_id: number; e2_index: number | null; plmn_mcc: string; plmn_mnc: string; position: number[]; is_active: boolean; color: number[] | null;
  a3_enabled: boolean | null; a3_offset_db: number | null; a3_hys_db: number | null; a3_ttt_ms: number | null; f_scene_uuid: string; f_gnb_config_template_uuid: string | null; config_template?: GnbConfigTemplate | null; dus: Du[];
}
export interface UeTraffic { ue_traffic_uuid: string; pattern: string; rate_mbps: number; schedule: number[][] | null; bearer_id: number; }
export interface Ue {
  ue_uuid: string; name: string; antenna_height_m: number; qos_5qi: number; color: number[]; loop: boolean; speed_mps: number | null;
  f_scene_uuid: string; f_antenna_preset_uuid: string | null; antenna_preset?: AntennaPreset | null;
  waypoints: [number, number, number, number][]; traffic: UeTraffic[]; active_windows: [number, number][];
  presence_restricted?: boolean;
}
export interface SceneRun {
  scene_run_uuid: string; mode: 'live' | 'cached'; speed_x: number; sim_dt_ms: number; duration_sec: number;
  /** 2026-09-28:只有三種。有沒有預算看 cache_path;上一次怎麼結束看 last_result */
  status: 'idle' | 'precomputing' | 'running'; last_result?: '' | 'done' | 'stopped' | 'failed'; cache_path: string; e2_node_id: string;
  started_at: string | null; stopped_at: string | null; notes: string; f_scene_uuid: string; knobs?: Record<string, unknown>;
}
export interface SceneTree { scene: Scene & { ground_material?: Material; gnb_antenna_preset?: AntennaPreset | null; ue_antenna_preset?: AntennaPreset | null }; buildings: Building[]; gnbs: Gnb[]; neighbor_seeds: unknown[]; ues: Ue[]; run: SceneRun | null; }
export interface RunKnob { run_knob_uuid: string; key: string; value: unknown; f_scene_run_uuid: string; }
export interface GnbConfigTemplate {
  gnb_config_template_uuid: string; name: string; source: string; notes: string; plmn_mcc: string; plmn_mnc: string;
  a3_enabled: boolean; a3_offset_db: number; a3_hys_db: number; a3_ttt_ms: number; band: string; center_frequency_ghz: number; bandwidth_mhz: number; power_dbm: number; tilt_deg: number;
  cells_per_gnb: number; azimuth_step_deg: number; f_du_config_template_uuid: string | null; f_antenna_preset_uuid: string | null;
}
