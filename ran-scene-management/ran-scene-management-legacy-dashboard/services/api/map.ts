import { omniverseApiClient } from '@/services/api/omniverse';
import { OMNIVERSE_API_URL } from '@/config';

// OpenStreetMap → USD 地圖場景 API(Omniverse backend :8001 RAN/Map/MapController)

export interface MapRow {
  name: string;
  label: string;
  min_lon: number;
  min_lat: number;
  max_lon: number;
  max_lat: number;
  usd_path: string;
  mesh_url: string;      // 匯入地圖才有：原始 .glb 的相對路徑（空字串 = OSM 產生的地圖）
  indoor_mode: boolean;  // 室內掃描：天花板收起、gNB 視覺尺寸縮小
  gnb_visual_scale: number;
  status: string;        // pending | ready | failed
  active: boolean;       // 是否為當前套用到場景的地圖
  error: string;
  building_count: number;
  height_max_m: number;
  extent_ew_m: number;
  extent_ns_m: number;
  created_at: string;
  updated_at: string;
}

export interface GenerateMapInput {
  name: string;
  label?: string;
  min_lon: number;
  min_lat: number;
  max_lon: number;
  max_lat: number;
}

export interface GeocodeResult {
  display_name: string;
  name: string;
  type: string;
  lat: number;
  lon: number;
  bbox: { min_lon: number; min_lat: number; max_lon: number; max_lat: number };
}

// 地標名稱 → 候選地點(座標 + 建議 bbox);後端 proxy Nominatim
export const geocodeLandmark = async (query: string): Promise<GeocodeResult[]> => {
  const res = await omniverseApiClient.post<{ data: { results: GeocodeResult[] } }>(
    '/api/v0.1/RAN/Map/MapController/geocode',
    { query, limit: 5 },
    { timeout: 30000 },
  );
  return res.data.data.results;
};

export const generateMap = async (input: GenerateMapInput): Promise<MapRow> => {
  // 抓 OSM(Overpass 公開服務,偶爾慢)+ 轉 USD 可能超過預設 30s,放寬到 3 分鐘
  const res = await omniverseApiClient.post<{ data: MapRow }>(
    '/api/v0.1/RAN/Map/MapController/generate',
    input,
    { timeout: 180000 },
  );
  return res.data.data;
};

export const listMaps = async (): Promise<MapRow[]> => {
  const res = await omniverseApiClient.post<{ data: { maps: MapRow[] } }>(
    '/api/v0.1/RAN/Map/MapController/list',
    {},
  );
  return res.data.data.maps;
};

export interface ApplyResult {
  name: string;
  usd_path: string;
  gnbs: number;
  ues: number;
  /** 是否已把 Mitsuba 場景推給 Sionna（沒有材質分類的地圖會是 false） */
  physics_pushed: boolean;
  physics_error: string;
}

export const applyMapToScene = async (name: string): Promise<ApplyResult> => {
  const res = await omniverseApiClient.post<{ data: ApplyResult }>(
    '/api/v0.1/RAN/Map/MapController/apply_to_scene',
    { name },
    { timeout: 180000 },
  );
  return res.data.data;
};

export interface IndoorSetupResult {
  name: string;
  grid: { walkable_area_m2: number; cell_m: number; clearance_m: number };
  path: { waypoint_count: number; path_length_m: number };
  changes: {
    ues: { name: string; to: [number, number, number]; target_height_m: number; waypoints: number }[];
    gnbs: { name: string; to: [number, number, number]; power_dbm: number }[];
  };
  gnb_visual_scale: number;
  physics_pushed: boolean;
  physics_error: string;
}

/**
 * 把場景切換成室內尺度：UE 降到真人身高並沿走廊巡走（A* 不穿牆）、
 * gNB 移進室內並縮小視覺尺寸、天花板收起，同時推 Kit 與 Sionna。
 */
export const setupIndoor = async (
  name: string,
  opts: { ue_height_m?: number; gnb_height_m?: number; gnb_power_dbm?: number;
          gnb_visual_scale?: number; dry_run?: boolean } = {},
): Promise<IndoorSetupResult> => {
  const res = await omniverseApiClient.post<{ data: IndoorSetupResult }>(
    '/api/v0.1/RAN/Map/MapController/setup_indoor',
    { name, ...opts },
    { timeout: 300000 },
  );
  return res.data.data;
};

export interface PlannedPath {
  waypoints: [number, number, number][];  // [x, 0, z]
  waypoint_count: number;
  path_length_m: number;
  direct_distance_m: number;
  detour_ratio: number;
  start_snapped: boolean;
  goal_snapped: boolean;
  buildings: number;
}

/** A→B 繞過建築的路徑規劃(後端 A*)。from/to 為 [x, z]。 */
export const planPath = async (
  name: string,
  from: [number, number],
  to: [number, number],
): Promise<PlannedPath> => {
  const res = await omniverseApiClient.post<{ data: PlannedPath }>(
    '/api/v0.1/RAN/Map/MapController/plan_path',
    { name, from, to },
    { timeout: 60000 },
  );
  return res.data.data;
};

export const detachMap = async (): Promise<void> => {
  await omniverseApiClient.post('/api/v0.1/RAN/Map/MapController/detach', {});
};

export const deleteMap = async (name: string): Promise<void> => {
  await omniverseApiClient.post('/api/v0.1/RAN/Map/MapController/delete', { name });
};

// ── GLB/glTF 網格匯入 ────────────────────────────────────
export type MaterialMode = 'conservative' | 'legacy_color';

export interface MaterialEvidence {
  mode: string;
  proven_area_pct: number;
  fallback_area_pct: number;
  fallback_material: string;
  fallback_rationale: string;
}

export interface MaterialDiagnostics {
  wood_boundary_density_pct: number;
  wood_boundary_isolated_pct: number;
  wood_boundary_reliable: boolean;
  note: string;
}

export interface RadioMaterials {
  materials: Record<string, { faces: number; area_m2: number; area_pct: number }>;
  evidence: MaterialEvidence;
  diagnostics: MaterialDiagnostics;
  mitsuba?: { holes_capped: number; face_count: number; materials: Record<string, unknown> };
  error?: string;
}

export interface GlbImportStats {
  mesh_count: number;
  triangle_count: number;
  vertex_count: number;
  material_count: number;
  texture_count: number;
  extent_ew_m: number;
  extent_ns_m: number;
  height_max_m: number;
  usd_path: string;
  texture_dir: string;
  size_bytes: number;
}

export interface ImportGlbInput {
  file: File;
  name: string;
  label?: string;
  scale?: number;
  recenter?: boolean;
  materialMode?: MaterialMode;
  onProgress?: (percent: number) => void;
}

/**
 * 上傳 .glb → 後端轉成 USD 並註冊為一張地圖，之後就能用 applyMapToScene 套用。
 * 走 multipart 而非 JSON：掃描檔動輒數十 MB，base64 會膨脹 1/3。
 */
export const importGlb = async ({
  file, name, label, scale = 1, recenter = true,
  materialMode = 'conservative', onProgress,
}: ImportGlbInput): Promise<MapRow & {
  import_stats: GlbImportStats;
  radio_materials: RadioMaterials | null;
}> => {
  const form = new FormData();
  form.append('file', file);
  form.append('name', name);
  if (label) form.append('label', label);
  form.append('scale', String(scale));
  form.append('recenter', String(recenter));
  form.append('material_mode', materialMode);

  const res = await omniverseApiClient.post<{
    data: MapRow & { import_stats: GlbImportStats; radio_materials: RadioMaterials | null };
  }>(
    '/api/v0.1/RAN/Map/MapController/import_glb',
    form,
    {
      // 覆蓋 client 預設的 application/json，讓瀏覽器自己帶 multipart boundary
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000, // 大檔上傳 + 轉檔，放寬到 5 分鐘
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
      },
    },
  );
  return res.data.data;
};

/** mesh_url(相對路徑)→ 可直接餵給 GLTFLoader 的絕對 URL。 */
export const meshAbsoluteUrl = (meshUrl: string): string =>
  meshUrl ? `${OMNIVERSE_API_URL}${meshUrl}` : '';
