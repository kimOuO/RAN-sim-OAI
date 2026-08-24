// UE 執行期(live)位置 —— 直接問 UE service,不經 Omniverse DB。
//
// 為什麼需要這支:UeLifecycleManager 每個 tick 算完位置後只推給 RU 與 Kit(3D),
// **不寫回 Omniverse DB**。Scene Layout 的 2D 畫布輪詢 DB,拿到的永遠是出生點,
// 於是「3D 會動、2D 不動」。這支拿的是執行期真值,兩邊才會一致。
import axios from 'axios';
import { UE_BASE_URL } from '@/config';

const ueClient = axios.create({
  baseURL: UE_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

export interface LiveUeSnapshot {
  simRunning: boolean;
  /** ue_id → [x, y, z](執行期座標) */
  positions: Record<string, [number, number, number]>;
  /** ue_id → serving cell,畫布要標色時可用 */
  servingCells: Record<string, string>;
  /** ue_id → thread 狀態(RUNNING / STANDBY=掉話選網中 / STOPPED) */
  states: Record<string, string>;
}

interface RawThread {
  ue_id: string;
  state: string;
  serving_cell?: string;
  position?: { x: number; y: number; z: number };
}

export const fetchLiveUePositions = async (): Promise<LiveUeSnapshot> => {
  const r = await ueClient.post<{
    data: { sim_running: boolean; threads: RawThread[] };
  }>('/api/v0.1/UE/Status/read', {}, { timeout: 4000 });
  const d = r.data?.data;
  const positions: Record<string, [number, number, number]> = {};
  const servingCells: Record<string, string> = {};
  const states: Record<string, string> = {};
  for (const t of d?.threads ?? []) {
    if (t.position) positions[t.ue_id] = [t.position.x, t.position.y, t.position.z];
    if (t.serving_cell) servingCells[t.ue_id] = t.serving_cell;
    if (t.state) states[t.ue_id] = t.state;
  }
  return { simRunning: !!d?.sim_running, positions, servingCells, states };
};
