import { INGEST_API } from '@/config';
import { post } from '@/services/clients/apiClient';
import type { Building } from '@/types/registry';
import type { GeocodeResult, LatLon, OsmBuildResult, OsmBuilding, OsmMapAsset, OsmPreview, ScanAsset } from '@/types/geometry';

const O = `${INGEST_API}/Render_osm_footprint`;
/** 地標 → 候選地點(後端 proxy Nominatim) */
export const geocodeLandmark = async (query: string) => (await post<{ results: GeocodeResult[] }>(`${O}/OsmFootprintImporter/geocode`, { query, limit: 5 }, { timeoutMs: 30_000 })).results;
/** 抓 OSM(Overpass)→ Mitsuba;可能要 1–3 分鐘 */
export const generateOsmMap = (body: { name: string; label?: string; min_lon: number; min_lat: number; max_lon: number; max_lat: number }) => post<OsmMapAsset>(`${O}/OsmFootprintImporter/generate`, body, { timeoutMs: 240_000 });
export const listOsmMaps = () => post<OsmMapAsset[]>(`${O}/OsmMapAssetReader/read`, {});
export const attachOsmToScene = (osm_map_asset_uuid: string, scene_uuid: string) => post<Building>(`${O}/OsmMapAssetController/attach_to_scene`, { osm_map_asset_uuid, scene_uuid });

const E = `${O}/OsmMapEditor`;
/** 範圍多邊形 → 範圍內的建築(Overpass,數秒到一分鐘) */
export const previewOsmArea = (polygon: LatLon[]) => post<OsmPreview>(`${E}/preview`, { polygon }, { timeoutMs: 180_000 });
/** 使用者編輯過的建築 → Mitsuba,並設成場景的幾何來源 */
export const buildOsmScene = (body: { scene_uuid: string; name: string; polygon: LatLon[]; buildings: OsmBuilding[] }) => post<OsmBuildResult>(`${E}/build_scene`, body, { timeoutMs: 180_000 });

const S = `${INGEST_API}/Render_scan_mesh`;
/** 上傳掃描 GLB(multipart)→ 材質分類 → Mitsuba */
export async function importScanGlb(file: File, name: string, materialMode: 'conservative' | 'legacy_color'): Promise<ScanAsset> {
  const fd = new FormData(); fd.append('file', file); fd.append('name', name); fd.append('material_mode', materialMode);
  const ctrl = new AbortController(); const t = setTimeout(() => ctrl.abort(), 600_000);
  try {
    const res = await fetch(`${S}/ScanMeshImporter/import_glb`, { method: 'POST', body: fd, signal: ctrl.signal });
    const json = await res.json() as { success: boolean; message: string; errors?: unknown; data: ScanAsset };
    if (!json.success) throw new Error(`${json.message}${json.errors ? `: ${JSON.stringify(json.errors)}` : ''}`);
    return json.data;
  } finally { clearTimeout(t); }
}
/** 場景幾何改用這個掃描模型 */
export const setSceneScanGeometry = (scan_asset_uuid: string, scene_uuid: string) => post<unknown>(`${S}/ScanAssetController/use_for_scene`, { scan_asset_uuid, scene_uuid });
