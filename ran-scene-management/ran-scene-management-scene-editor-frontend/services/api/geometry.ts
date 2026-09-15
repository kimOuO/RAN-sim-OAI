import { INGEST_API } from '@/config';
import { post } from '@/services/clients/apiClient';
import type { Building } from '@/types/registry';
import type { GeocodeResult, OsmMapAsset } from '@/types/geometry';

const O = `${INGEST_API}/Render_osm_footprint`;
/** 地標 → 候選地點(後端 proxy Nominatim) */
export const geocodeLandmark = async (query: string) => (await post<{ results: GeocodeResult[] }>(`${O}/OsmFootprintImporter/geocode`, { query, limit: 5 }, { timeoutMs: 30_000 })).results;
/** 抓 OSM(Overpass)→ Mitsuba;可能要 1–3 分鐘 */
export const generateOsmMap = (body: { name: string; label?: string; min_lon: number; min_lat: number; max_lon: number; max_lat: number }) => post<OsmMapAsset>(`${O}/OsmFootprintImporter/generate`, body, { timeoutMs: 240_000 });
export const listOsmMaps = () => post<OsmMapAsset[]>(`${O}/OsmMapAssetReader/read`, {});
export const attachOsmToScene = (osm_map_asset_uuid: string, scene_uuid: string) => post<Building>(`${O}/OsmMapAssetController/attach_to_scene`, { osm_map_asset_uuid, scene_uuid });
