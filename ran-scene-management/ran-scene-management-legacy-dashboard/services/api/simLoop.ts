// 4-system 拆分後：tick driver / sim 控制權限轉移到 DU
// 舊 path /api/v0.1/RanpSim/RanSignal/SimLoop/* → 新 /api/v0.1/DU/Tick/TickController/*
import { duClient, ueClient } from '@/services/clients/httpClient';
import type { SetupUERequest, SimStatus } from '@/types';

// Stage 5A — 統一 sim 入口。/editor live_db + /scenarios 都打這個。
// RANsim-UE SimController 接管整段 C.1〜G(scene-apply / UE attach / DU tick / lifecycle)。
export const startUnifiedSim = async (params: {
  source: 'live_db' | 'scenario';
  scenario_id?: string;
  speed_x?: number;
  sim_dt_ms?: number;   // scenarios=100, editor=500(default)
}): Promise<any> => {
  const body: Record<string, any> = { source: params.source };
  if (params.scenario_id) body.scenario_id = params.scenario_id;
  if (params.speed_x !== undefined) body.speed_x = params.speed_x;
  if (params.sim_dt_ms !== undefined) body.sim_dt_ms = params.sim_dt_ms;
  const r = await ueClient.post('/api/v0.1/UE/Sim/SimController/start', body);
  return (r.data as any)?.data ?? r.data;
};

export const stopUnifiedSim = async (): Promise<any> => {
  const r = await ueClient.post('/api/v0.1/UE/Sim/SimController/stop', {});
  return (r.data as any)?.data ?? r.data;
};

export const setupUE = async (ueTrajectories: SetupUERequest['ues']): Promise<void> => {
  // 只發送有有效軌跡的 UE（至少 2 個 waypoint）
  const validUEs = ueTrajectories.filter(ue => ue.waypoints && ue.waypoints.length >= 2);

  // DU register_ue schema: { ue_id, serving_cell?, sinr_db?, rsrp_dbm?, qos_5qi? }
  // Dashboard 的 ue.name → backend 的 ue_id（trajectory 由 RU update_ues + scene 端管理，
  // 不在 DU 的 register_ue 範圍）
  for (const ue of validUEs) {
    await duClient.post('/api/v0.1/DU/Tick/TickController/register_ue', {
      ue_id: ue.name,
    });
  }
};

export const stopSim = async (): Promise<void> => {
  await duClient.post('/api/v0.1/DU/Tick/TickController/stop', {});
};

export const getStatus = async (): Promise<SimStatus> => {
  const response = await duClient.post<{ data: SimStatus }>(
    '/api/v0.1/DU/Tick/TickController/read',
    {}
  );
  return response.data.data;
};

// Phase A — 改 DU sim_tick_ms,壓縮整段 RAN tick wall-clock 節奏。
// tick_ms 500=1x, 250=2x, 125=4x, 50=10x。下一輪 tick 即生效。
//
// 只設 DU — CU + e2adapter 會 background pull 自動跟上(~4s wall 全鏈路收斂)。
export const setSimSpeed = async (tickMs: number): Promise<{ sim_tick_ms: number }> => {
  const response = await duClient.post<{ data: { sim_tick_ms: number } }>(
    '/api/v0.1/DU/Tick/TickController/set_speed',
    { tick_ms: tickMs }
  );
  return response.data.data;
};

// Kit (omniver_kit) 在 :8080 直接 expose live UE position（USD time-sample 持續 advance）。
// 比 Omniver-RAN listUes（DB 快照）即時。
const KIT_LIVE_URL = process.env.NEXT_PUBLIC_KIT_LIVE_URL || 'http://localhost:8080/ues';

export const fetchUEPositions = async (): Promise<Record<string, [number, number, number]>> => {
  try {
    const r = await fetch(KIT_LIVE_URL, { method: 'GET' });
    if (!r.ok) return {};
    const ues = await r.json() as Array<{ name: string; position?: { x: number; y: number; z: number } }>;
    const out: Record<string, [number, number, number]> = {};
    for (const ue of ues) {
      if (ue.name && ue.position) {
        out[ue.name] = [ue.position.x, ue.position.y, ue.position.z];
      }
    }
    return out;
  } catch {
    return {};
  }
};
