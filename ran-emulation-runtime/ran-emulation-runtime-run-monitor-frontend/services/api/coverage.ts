import { REGISTRY_API } from '@/config';
import { post } from '@/services/clients/apiClient';

/** 覆蓋熱圖(GPU 光追);與編輯器第 2 步用的是同一支 registry 端點 */
export interface CoverageResult {
  compute_ms: number;
  grid: { x_range: number[]; z_range: number[]; x_step: number; z_step: number; sample_height_m: number; n_rows: number; n_cols: number };
  summary: { cells: string[]; cell_names: string[]; best_rsrp_dbm: (number | null)[][]; sinr_db: (number | null)[][]; best_cell: (number | null)[][] };
}

export const computeCoverage = (scene_uuid: string, opts: { sample_height_m: number; step_m?: number | null; margin_m?: number }) =>
  post<CoverageResult>(`${REGISTRY_API}/Field_scene/SceneGeometryReader/coverage`, { scene_uuid, ...opts }, { timeoutMs: 600_000 });

/** 場景幾何的實際邊界(含掃描模型):3D 取景與覆蓋範圍都用它 */
export const sceneBounds = (scene_uuid: string) =>
  post<{ x_range: number[] | null; z_range: number[] | null }>(`${REGISTRY_API}/Field_scene/SceneGeometryReader/bounds`, { scene_uuid }, { timeoutMs: 180_000 });
