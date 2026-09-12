export type AsyncStatus = 'idle' | 'loading' | 'success' | 'error';

export interface AsyncState<T> {
  data: T | null;
  status: AsyncStatus;
  error: Error | null;
  refetch: () => void;
}

export interface ApiError {
  success: false;
  message: string;
  errors?: Record<string, unknown>;
}

export interface ApiSuccess<T> {
  success: true;
  message: string;
  data: T;
}

export type ApiResponse<T> = ApiSuccess<T> | ApiError;

export interface UsdAsset {
  asset_uuid: string;
  preset_id: string;
  object_type: 'building' | 'ue' | 'obstacle' | 'gnb';
  label: string;
  description?: string;
  usd_path: string;
  default_size?: [number, number, number] | null;
  default_color?: [number, number, number] | null;
  default_scale?: [number, number, number] | null;
  active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface Building {
  name: string;
  position: [number, number, number];
  size: [number, number, number];
  color: [number, number, number];
  usd?: string;
  usd_path?: string;
  preset_type?: string;
  scale?: [number, number, number];
  rotation_xyz_deg?: [number, number, number];
  target_height_m?: number;
}

export interface Ground {
  material: string;
  size: [number, number];
}

export interface GNB {
  name: string;
  cell_id?: string;
  position: [number, number, number];
  color: [number, number, number];
  frequency_ghz: number;
  power_dbm: number;
  bandwidth_mhz: number;
  active?: boolean;
  cells?: Array<{ pci: number; azimuth_deg: number }>;
}

export interface UE {
  name: string;
  prim_path?: string;
  position: [number, number, number];
  color: [number, number, number];
  usd?: string;
  scale?: [number, number, number];
  speed_mps: number;
  waypoints?: Array<[number, number, number]>;
}

export interface SceneLayout {
  ground?: Ground;
  buildings: Building[];
  gnbs: any[];
  ues: any[];
  environment?: { template_usd: string; name: string };
  skip_buildings?: boolean;
  map_footprints?: { points: [number, number][]; height: number }[];
}

export interface SceneAntennaConfig {
  gnb_antenna_pattern?: 'tr38901' | 'iso' | 'dipole' | 'hw_dipole' | 'vh_dipole';
  gnb_polarization?: 'V' | 'H' | 'VH' | 'cross';
  ue_antenna_pattern?: 'tr38901' | 'iso' | 'dipole' | 'hw_dipole' | 'vh_dipole';
  ue_polarization?: 'V' | 'H' | 'VH' | 'cross';
  gnb_array_rows?: number;
  gnb_array_cols?: number;
  ue_array_rows?: number;
  ue_array_cols?: number;
}

export interface SceneConfig {
  scene_id?: string;
  ground?: Ground;
  buildings?: Building[];
  gnbs?: GNB[];
  ues?: UE[];
  scene_antenna_config?: SceneAntennaConfig;
}

export interface InitSceneResponse {
  session_uuid: string;
  scene_id: string;
}

export interface SetupUERequest {
  ues: Array<{
    name: string;
    waypoints: Array<[number, number, number]>;
    speed_mps: number;
    loop?: boolean;
  }>;
}

export interface UESignalData {
  ue_name?: string;
  name?: string;
  rsrp_dbm?: number;
  sinr_db?: number;
  serving_cell?: string;
  position?: [number, number, number];
  x?: number;
  y?: number;
  z?: number;
  mimo_rank?: number;
  mimo_streams_sinr_db?: number[];
  mimo_streams_mcs?: number[];
  throughput_dl_mbps?: number;
  throughput_ul_mbps?: number;
  mcs_dl?: number;
  prb_used_dl?: number;
  rsrp_map?: Record<string, number>;
  serving_gnb?: string;
  serving_pci?: number;
  serving_cell_id?: string;
}

export interface SimStatus {
  running: boolean;
  current_tick?: number;
  ues?: UESignalData[];
  wall_tick_ms?: number;
  sim_dt_ms?: number;
  sim_speed_x?: number;
}

export interface SceneSnapshot {
  buildings?: Building[];
  gnbs?: GNB[];
  obstacles?: any[];
}

export interface PlaybackSession {
  session_uuid: string;
  scene_id: string;
  timestamp: string;
  frame_count: number;
  scene_snapshot?: SceneSnapshot;
  // Phase B B.5 — fast_cached session metadata
  mode?: 'live' | 'fast_cached';
  scenario_id?: string;
  time_compression_ratio?: number;
}

export interface HandoverEventRecord {
  ho_uuid: string;
  ue_name: string;
  source_cell: string;
  target_cell: string;
  trigger: string;
  status: string;
  event_ts: string | null;
}

export interface ControlActionRecord {
  id: number;
  ric_req_id: Record<string, unknown>;
  control_style: number;
  control_action_id: number;
  action_label: string;
  ue_name: string | null;
  cell_id: string | null;
  payload_json: Record<string, unknown>;
  outcome: string;
  error: string | null;
  action_ts: string | null;
}

export interface CellStateSnapshot {
  cell_id: string;
  gnb_id?: string | null;
  pci?: number | null;
  is_active: boolean;
  prb_quota: {
    min_prb?: number | null;
    max_prb?: number | null;
    dedicated_prb?: number | null;
  } | null;
}

export interface PlaybackFrame {
  tick: number;
  ues: UESignalData[];
  handovers?: HandoverEventRecord[];
  control_actions?: ControlActionRecord[];
  cell_states?: CellStateSnapshot[];
  scene_snapshot?: SceneSnapshot;
  // Phase B B.5 — fast_cached session metadata
  mode?: 'live' | 'fast_cached';
  scenario_id?: string;
  time_compression_ratio?: number;
}
