import { omniverseApiClient } from '@/services/api/omniverse';

// OpenStreetMap → USD 地圖場景 API(Omniverse backend :8001 RAN/Map/MapController)

export interface MapRow {
  name: string;
  label: string;
  min_lon: number;
  min_lat: number;
  max_lon: number;
  max_lat: number;
  usd_path: string;
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

export const applyMapToScene = async (
  name: string,
): Promise<{ name: string; usd_path: string; gnbs: number; ues: number }> => {
  const res = await omniverseApiClient.post<{
    data: { name: string; usd_path: string; gnbs: number; ues: number };
  }>('/api/v0.1/RAN/Map/MapController/apply_to_scene', { name });
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
