import { REGISTRY_API } from '@/config';
import { post } from '@/services/clients/apiClient';
import type { Scene, SceneTree } from '@/types/registry';

export const listScenes = () => post<Scene[]>(`${REGISTRY_API}/Field_scene/SceneReader/read`, {});
export const getScene = (scene_uuid: string) => post<Scene>(`${REGISTRY_API}/Field_scene/SceneReader/read`, { scene_uuid });
export const getSceneTree = (scene_uuid: string) => post<SceneTree>(`${REGISTRY_API}/Field_scene/SceneReader/read_full_tree`, { scene_uuid });
export const createScene = (body: Partial<Scene>) => post<Scene>(`${REGISTRY_API}/Field_scene/SceneController/create`, body);
export const updateScene = (scene_uuid: string, body: Partial<Scene>) => post<Scene>(`${REGISTRY_API}/Field_scene/SceneController/update`, { scene_uuid, ...body });
export const deleteScene = (scene_uuid: string) => post<{ deleted: number }>(`${REGISTRY_API}/Field_scene/SceneController/delete`, { scene_uuid });
/** 深複製整個場景(天線、RU 覆寫、UE 路徑與流量、run 設定都一起帶) */
export const duplicateScene = (scene_uuid: string, name: string) => post<Scene>(`${REGISTRY_API}/Field_scene/SceneController/duplicate`, { scene_uuid, name }, { timeoutMs: 60_000 });
/** 場景幾何網格(掃描 / OSM 的 Mitsuba 場景);畫布顯示用 */
export interface SceneMeshOp { op: 'translate' | 'scale' | 'rotate' | 'matrix'; v?: number[]; axis?: number[]; deg?: number }
export interface SceneMesh { shape_id: string; name: string; format: 'ply' | 'obj'; material: string; color: number[] | null; bytes: number; too_large: boolean; transform: SceneMeshOp[] }
export const listSceneMeshes = (scene_uuid: string) => post<SceneMesh[]>(`${REGISTRY_API}/Field_scene/SceneGeometryReader/meshes`, { scene_uuid });
/** 網格檔原始位元組(不是 JSON 包裝) */
export async function fetchSceneMeshFile(scene_uuid: string, shape_id: string): Promise<ArrayBuffer> {
  const res = await fetch(`${REGISTRY_API}/Field_scene/SceneGeometryReader/mesh_file`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ scene_uuid, shape_id }) });
  if (!res.ok) throw new Error(`mesh ${shape_id}: HTTP ${res.status}`);
  return res.arrayBuffer();
}
/** 覆蓋圖(physics 另建暫時 engine;列 = z 遞增、欄 = x 遞增) */
export interface CoverageResult {
  compute_ms: number;
  grid: { x_range: number[]; z_range: number[]; x_step: number; z_step: number; sample_height_m: number; n_rows: number; n_cols: number };
  summary: { cells: string[]; cell_names: string[]; best_rsrp_dbm: (number | null)[][]; sinr_db: (number | null)[][]; best_cell: (number | null)[][] };
}
export const computeCoverage = (scene_uuid: string, opts: { sample_height_m: number; step_m?: number | null; max_depth?: number; margin_m?: number }) =>
  post<CoverageResult>(`${REGISTRY_API}/Field_scene/SceneGeometryReader/coverage`, { scene_uuid, ...opts }, { timeoutMs: 600_000 });

/** 場景幾何的實際邊界(含掃描模型;只有 gNB/建築盒算不出來) */
export const sceneBounds = (scene_uuid: string) =>
  post<{ x_range: number[] | null; z_range: number[] | null }>(`${REGISTRY_API}/Field_scene/SceneGeometryReader/bounds`, { scene_uuid }, { timeoutMs: 180_000 });

export interface HeightMap { x_range: number[]; z_range: number[]; step_m: number; n_rows: number; n_cols: number; height_m: (number | null)[][] }
/** 每格的表面高度:明顯高於地面 = 建築,UE 隨機產生用它避障 */
export const sceneHeightMap = (scene_uuid: string, step_m = 4) =>
  post<HeightMap>(`${REGISTRY_API}/Field_scene/SceneGeometryReader/height_map`, { scene_uuid, step_m }, { timeoutMs: 300_000 });
