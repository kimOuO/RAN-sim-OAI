// API 包裝 — UE container (RANsim-UE) + CU 的 UE 相關操作
//
// 對應:
//   UE container :8105  /api/v0.1/UE/Trajectory/{set,clear,list}
//   UE container :8105  /api/v0.1/UE/Lifecycle/{sync,start,stop}
//   UE container :8105  /api/v0.1/UE/Status/read
//   CU :8101            /api/v0.1/CU/Session/SessionController/update_traffic_profile
import { ueClient, cuClient } from '@/services/clients/httpClient';

// ── Traffic profile schema ────────────────────────────────────
export type TrafficPattern = 'idle' | 'cbr' | 'bursty';

export interface TrafficProfile {
  pattern: TrafficPattern;
  rate_mbps?: number;     // CBR rate
  sdu_size?: number;      // bytes, default 1500
  bearer_id?: number;     // default 1
  // Bursty 之後再加 burst_size_kb / interval_ms
}

// ── Trajectory schema ─────────────────────────────────────────
// UE container 接受的 waypoints: [{x, y, z, t_ms}, ...]
export type TrajectoryMode = 'loop' | 'once' | 'stay';

export interface TrajectoryWaypoint {
  x: number;
  y: number;
  z: number;
  t_ms: number;   // 相對 trajectory start
}

// ── Helpers ───────────────────────────────────────────────────

/**
 * Convert /draw 頁的 [x,0,z] 二維 waypoints + speed_mps 換成 UE container schema 要的
 * [{x,y,z,t_ms},...]，t_ms 從 0 累計每段距離 / speed。
 */
export function buildWaypointsFromDraw(
  waypoints2d: [number, number, number][],
  speedMps: number,
): TrajectoryWaypoint[] {
  if (!waypoints2d.length) return [];
  if (speedMps <= 0) speedMps = 1.0;
  const out: TrajectoryWaypoint[] = [];
  let t_ms = 0;
  out.push({ x: waypoints2d[0][0], y: waypoints2d[0][1], z: waypoints2d[0][2], t_ms: 0 });
  for (let i = 1; i < waypoints2d.length; i++) {
    const dx = waypoints2d[i][0] - waypoints2d[i - 1][0];
    const dy = waypoints2d[i][1] - waypoints2d[i - 1][1];
    const dz = waypoints2d[i][2] - waypoints2d[i - 1][2];
    const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
    const dt_ms = Math.round((dist / speedMps) * 1000);
    t_ms += dt_ms;
    out.push({ x: waypoints2d[i][0], y: waypoints2d[i][1], z: waypoints2d[i][2], t_ms });
  }
  return out;
}

// ── UE container API ───────────────────────────────────────────

export async function setTrajectory(
  ue_id: string,
  waypoints: TrajectoryWaypoint[],
  mode: TrajectoryMode = 'loop',
): Promise<void> {
  await ueClient.post('/api/v0.1/UE/Trajectory/set', {
    ue_id,
    waypoints,
    mode,
  });
}

export async function clearTrajectory(ue_id: string): Promise<void> {
  await ueClient.post('/api/v0.1/UE/Trajectory/clear', { ue_id });
}

export async function ueSimStart(): Promise<void> {
  await ueClient.post('/api/v0.1/UE/Lifecycle/start', {});
}

export async function ueSimStop(): Promise<void> {
  await ueClient.post('/api/v0.1/UE/Lifecycle/stop', {});
}

export async function ueLifecycleSync(event: string, ue_id?: string): Promise<void> {
  await ueClient.post('/api/v0.1/UE/Lifecycle/sync', { event, ue_id });
}

export async function readUeStatus(): Promise<any> {
  const r = await ueClient.post('/api/v0.1/UE/Status/read', {});
  return r.data?.data;
}

// ── CU UeContext API ───────────────────────────────────────────

export async function updateTrafficProfile(
  ue_id: string,
  profile: TrafficProfile,
): Promise<void> {
  await cuClient.post('/api/v0.1/CU/Session/SessionController/update_traffic_profile', {
    ue_id,
    traffic_profile: profile,
  });
}
