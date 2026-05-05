function getRuntimeConfig() {
  if (typeof window !== 'undefined' && (window as any).__APP_CONFIG__) {
    return (window as any).__APP_CONFIG__;
  }
  return null;
}

// ── 4-system 拆分後每個 backend 自己的 base URL ──────────
// docker compose 的 default port mapping:
//   CU      :8101    DU      :8102
//   RU      :8103    Physics :8104
export const PHYSICS_BASE_URL = getRuntimeConfig()?.physicsUrl
  || process.env.NEXT_PUBLIC_PHYSICS_URL
  || 'http://localhost:8104';
export const CU_BASE_URL = getRuntimeConfig()?.cuUrl
  || process.env.NEXT_PUBLIC_CU_URL
  || 'http://localhost:8101';
export const DU_BASE_URL = getRuntimeConfig()?.duUrl
  || process.env.NEXT_PUBLIC_DU_URL
  || 'http://localhost:8102';
export const RU_BASE_URL = getRuntimeConfig()?.ruUrl
  || process.env.NEXT_PUBLIC_RU_URL
  || 'http://localhost:8103';

// 舊變數保留向後相容（很多既有 endpoint 還在 Physics），預設指 Physics
export const API_BASE_URL = getRuntimeConfig()?.apiBaseUrl
  || process.env.NEXT_PUBLIC_API_BASE_URL
  || PHYSICS_BASE_URL;
export const OMNIVERSE_API_URL = getRuntimeConfig()?.omniverseUrl
  || process.env.NEXT_PUBLIC_OMNIVERSE_URL
  || 'http://localhost:8001';
export const VNC_URL = getRuntimeConfig()?.vncUrl
  || process.env.NEXT_PUBLIC_VNC_URL
  || 'http://localhost:6080/vnc.html';
export const WS_URL = getRuntimeConfig()?.wsUrl
  || process.env.NEXT_PUBLIC_WS_URL
  || `ws://localhost:8104/ws/sim/live/`;

export const DEFAULT_FETCH_TIMEOUT_MS = 30000;
export const SIM_LOOP_TICK_MS = 500;

export const CANVAS_WIDTH = 800;
export const CANVAS_HEIGHT = 600;
export const SCENE_CONFIG_URL = '/scene_config.json';
