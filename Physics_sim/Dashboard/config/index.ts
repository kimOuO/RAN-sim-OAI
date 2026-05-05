function getRuntimeConfig() {
  if (typeof window !== 'undefined' && (window as any).__APP_CONFIG__) {
    return (window as any).__APP_CONFIG__;
  }
  return null;
}

export const API_BASE_URL = getRuntimeConfig()?.apiBaseUrl || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
export const OMNIVERSE_API_URL = getRuntimeConfig()?.omniverseUrl || process.env.NEXT_PUBLIC_OMNIVERSE_URL || 'http://localhost:8001';
export const VNC_URL = getRuntimeConfig()?.vncUrl || process.env.NEXT_PUBLIC_VNC_URL || 'http://localhost:6080/vnc.html';
export const WS_URL = getRuntimeConfig()?.wsUrl || process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/sim/live/';

export const DEFAULT_FETCH_TIMEOUT_MS = 30000;
export const SIM_LOOP_TICK_MS = 500;

export const CANVAS_WIDTH = 800;
export const CANVAS_HEIGHT = 600;
export const SCENE_CONFIG_URL = '/scene_config.json';
