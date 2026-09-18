/** building-geometry-ingest 的 DTO */
export interface GeocodeResult { display_name: string; name: string; type: string; lat: number; lon: number; bbox: { min_lon: number; min_lat: number; max_lon: number; max_lat: number }; }
export interface OsmMapAsset { osm_map_asset_uuid: string; name: string; label: string; min_lon: number; min_lat: number; max_lon: number; max_lat: number; origin_lat: number | null; origin_lon: number | null; mitsuba_xml: string; building_count: number; height_max_m: number; extent_ew_m: number; extent_ns_m: number; status: 'pending' | 'ready' | 'failed'; error: string; }
/** 地圖編輯:範圍多邊形 [lat, lon][] */
export type LatLon = [number, number];
/** 範圍內一棟建築(OSM 輪廓);材質 / 高度 / 是否納入由使用者逐棟調整 */
export interface OsmBuilding { id: string; name: string; outer: LatLon[]; inner: LatLon[][]; base_m: number; height_m: number; height_known: boolean; material: string; excluded?: boolean; }
export interface OsmPreview { buildings: OsmBuilding[]; area_m2: number; }
export interface OsmBuildResult { mitsuba_path: string; building_count: number; by_material: Record<string, number>; height_max_m: number; area_m2: number; origin_lat: number; origin_lon: number; }
export interface ScanAsset { scan_asset_uuid: string; name: string; status: 'pending' | 'ready' | 'failed'; mitsuba_xml: string; error: string; }
