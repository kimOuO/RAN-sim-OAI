// Coverage map（Sionna RadioMapSolver）在 Physics_sim
import { physicsClient } from '@/services/clients/httpClient';

export interface GridSpec {
  x_range: [number, number];
  x_step: number;
  z_range: [number, number];
  z_step: number;
  sample_height_m?: number;
}

export interface CoverageRequest {
  scene_id: string;
  grid: GridSpec;
  include_sinr?: boolean;
  max_depth?: number;
  null_threshold_dbm?: number;
}

export interface CoverageGnb {
  gnb_name: string;
  pci: number;
  cell_id: string;
  frequency_ghz: number;
  power_dbm: number;
  rsrp_dbm: (number | null)[][];
  sinr_db?: (number | null)[][];
}

export interface CoverageResponse {
  scene_id: string;
  ts: string;
  compute_ms: number;
  grid: {
    x_range: [number, number];
    x_step: number;
    z_range: [number, number];
    z_step: number;
    sample_height_m: number;
    n_rows: number;
    n_cols: number;
  };
  gnbs: CoverageGnb[];
}

export const computeCoverage = async (payload: CoverageRequest): Promise<CoverageResponse> => {
  const response = await physicsClient.post<{ data: CoverageResponse }>(
    '/api/v0.1/RanpSim/RanSignal/CoverageRunner/compute',
    payload
  );
  return response.data.data;
};
