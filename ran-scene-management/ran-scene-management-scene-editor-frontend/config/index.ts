export const REGISTRY_BASE_URL = process.env.NEXT_PUBLIC_REGISTRY_BASE_URL ?? 'http://localhost:8301';
export const INGEST_BASE_URL = process.env.NEXT_PUBLIC_INGEST_BASE_URL ?? 'http://localhost:8303';
export const ORCHESTRATOR_BASE_URL = process.env.NEXT_PUBLIC_ORCHESTRATOR_BASE_URL ?? 'http://localhost:8302';
export const REGISTRY_API = `${REGISTRY_BASE_URL}/api/v0.1/Network_element_registry`;
export const ORCHESTRATOR_API = `${ORCHESTRATOR_BASE_URL}/api/v0.1/Run_orchestrator`;
export const INGEST_API = `${INGEST_BASE_URL}/api/v0.1/Building_geometry_ingest`;
/** 畫布:1 單位 = 1 公尺;registry 座標 Y-up(x 東、y 上、z 南),與 Sionna/場景檔一致 */
export const CANVAS = { gridSize: 200, cellMarkerRadius: 1.2, ueMarkerRadius: 0.4 } as const;
