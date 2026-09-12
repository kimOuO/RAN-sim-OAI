function getRuntimeConfig() {
  if (typeof window !== 'undefined' && (window as any).__APP_CONFIG__) {
    return (window as any).__APP_CONFIG__;
  }
  return null;
}

/**
 * 跨機器存取時自動 swap localhost。
 * 若瀏覽器透過 e.g. http://10.3.0.217:3010 開 Dashboard，
 * 那它對 backend 的 fetch 也要走 10.3.0.217:8103，不能用 localhost
 *（瀏覽器的 localhost 是 user 自己的機器，不是 server）。
 */
function resolveHost(defaultUrl: string): string {
  if (typeof window === 'undefined') return defaultUrl;
  const h = window.location.hostname;
  if (h === 'localhost' || h === '127.0.0.1') return defaultUrl;
  return defaultUrl
    .replace(/\/\/localhost\b/, `//${h}`)
    .replace(/\/\/127\.0\.0\.1\b/, `//${h}`);
}

// ── 4-system 拆分後每個 backend 自己的 base URL ──────────
// docker compose 的 default port mapping:
//   CU      :8101    DU      :8102
//   RU      :8103    Physics :8104
// 注意：env value 也要過 resolveHost，否則跨機器存取（瀏覽器 hostname != localhost）會打不到
// docker-compose 把 NEXT_PUBLIC_*_URL 都設成 localhost，但 windows browser 的 localhost 不是 server
export const PHYSICS_BASE_URL = getRuntimeConfig()?.physicsUrl
  || resolveHost(process.env.NEXT_PUBLIC_PHYSICS_URL || 'http://localhost:8104');
export const CU_BASE_URL = getRuntimeConfig()?.cuUrl
  || resolveHost(process.env.NEXT_PUBLIC_CU_URL || 'http://localhost:8101');
export const DU_BASE_URL = getRuntimeConfig()?.duUrl
  || resolveHost(process.env.NEXT_PUBLIC_DU_URL || 'http://localhost:8102');
export const RU_BASE_URL = getRuntimeConfig()?.ruUrl
  || resolveHost(process.env.NEXT_PUBLIC_RU_URL || 'http://localhost:8103');
export const E2_ADAPTER_BASE_URL = getRuntimeConfig()?.e2AdapterUrl
  || resolveHost(process.env.NEXT_PUBLIC_E2_ADAPTER_URL || 'http://localhost:8201');
// UE container (RANsim-UE, port 8105) — active UE object 化, 跑 traffic + measurement
export const UE_BASE_URL = getRuntimeConfig()?.ueUrl
  || resolveHost(process.env.NEXT_PUBLIC_UE_URL || 'http://localhost:8105');

// 舊變數保留向後相容（很多既有 endpoint 還在 Physics），預設指 Physics
export const API_BASE_URL = getRuntimeConfig()?.apiBaseUrl
  || (process.env.NEXT_PUBLIC_API_BASE_URL ? resolveHost(process.env.NEXT_PUBLIC_API_BASE_URL) : PHYSICS_BASE_URL);
export const OMNIVERSE_API_URL = getRuntimeConfig()?.omniverseUrl
  || resolveHost(process.env.NEXT_PUBLIC_OMNIVERSE_URL || 'http://localhost:8001');
// 劇本/場景倉庫來源:預設 = Omniverse;設 NEXT_PUBLIC_SCENARIO_STORE_URL(如 Physics :8104)
// 即可讓 Dashboard 的劇本 CRUD 改打 physics_db store(脫離 Omniverse)。端點形狀相同。
export const SCENARIO_STORE_API_URL =
  (getRuntimeConfig() as any)?.scenarioStoreUrl
  || (process.env.NEXT_PUBLIC_SCENARIO_STORE_URL
        ? resolveHost(process.env.NEXT_PUBLIC_SCENARIO_STORE_URL)
        : OMNIVERSE_API_URL);
export const VNC_URL = getRuntimeConfig()?.vncUrl
  || resolveHost(process.env.NEXT_PUBLIC_VNC_URL || 'http://localhost:6080/vnc.html');

export const DEFAULT_FETCH_TIMEOUT_MS = 30000;
export const SIM_LOOP_TICK_MS = 500;

export const CANVAS_WIDTH = 800;
export const CANVAS_HEIGHT = 600;
export const SCENE_CONFIG_URL = '/scene_config.json';
