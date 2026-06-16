// Phase B B.6 — Scenario API client (Omniverse + Physics + RU + UE + DU orchestration).
import { duClient, physicsClient, ruClient, ueClient } from '@/services/clients/httpClient';
import { omniverseApiClient } from '@/services/api/omniverse';

export interface ScenarioRow {
  scenario_id: string;
  scene_id: string;
  duration_sec: number;
  tick_ms: number;
  ue_count: number;
  precompute_status: 'pending' | 'running' | 'ready' | 'failed';
  precompute_progress: number;
  precompute_error: string;
  cache_path: string;
  cache_size_bytes: number;
  created_at: string;
  updated_at: string;
}

export const listScenarios = async (): Promise<ScenarioRow[]> => {
  const r = await omniverseApiClient.post('/api/v0.1/RAN/Scenario/ScenarioController/list', {});
  return r.data?.data?.scenarios ?? [];
};

export const readScenario = async (scenarioId: string): Promise<any> => {
  const r = await omniverseApiClient.post(
    '/api/v0.1/RAN/Scenario/ScenarioController/read',
    { scenario_id: scenarioId },
  );
  return r.data?.data;
};

export const uploadScenario = async (scenarioJson: unknown): Promise<ScenarioRow> => {
  const r = await omniverseApiClient.post('/api/v0.1/RAN/Scenario/ScenarioController/upload', scenarioJson);
  return r.data?.data;
};

/**
 * 把劇本拓樸寫進 Omniverse 場景表(Gnb/Ue/Building)並推 3D。
 * ★ 會覆蓋目前場景表 —— Scene Editor「選劇本即套用」用,讓 Scene Layout 反映劇本。
 */
export const applyScenarioToScene = async (
  scenarioId: string
): Promise<{ gnbs: number; ues: number; buildings: number; kit_pushed: boolean }> => {
  const r = await omniverseApiClient.post(
    '/api/v0.1/RAN/Scenario/ScenarioController/apply_to_scene',
    { scenario_id: scenarioId }
  );
  return r.data?.data;
};

export const deleteScenario = async (scenarioId: string): Promise<void> => {
  await omniverseApiClient.post('/api/v0.1/RAN/Scenario/ScenarioController/delete', { scenario_id: scenarioId });
};

// Trigger precompute — 兩步:Omniverse 標 pending,Physics 真正 spawn subprocess。
export const triggerPrecompute = async (scenarioId: string): Promise<void> => {
  await omniverseApiClient.post('/api/v0.1/RAN/Scenario/ScenarioController/precompute', { scenario_id: scenarioId });
  await physicsClient.post('/api/v0.1/Physics/Precompute/run', { scenario_id: scenarioId });
};

// 強制 RU 切到 live mode — sim 起來後呼叫覆寫 scenario_driver 自動套的 cached。
// 用途:cached SINR 公式有 bug 時繞過,或想跑物理真實 ray tracing 對照。
export const forceRuLiveMode = async (): Promise<void> => {
  await ruClient.post('/api/v0.1/RU/Config/RuController/set_channel_mode', { mode: 'live' });
};

// Orchestrate Start Fast Run — 完整序列。
// 假設前提:UE 已透過 /editor flow 跑過 attach(CU UE session 存在)。
export interface StartFastRunOptions {
  scenarioId: string;
  targetWallTickMs: number;   // e.g. 250 = 2x compression for scenario tick_ms=500
  sceneId: string;
  sessionUuid: string;
  timeCompressionRatio: number;
}

export const startFastRun = async (opts: StartFastRunOptions) => {
  // 1. 切 RU 到 cached mode + load cache
  await ruClient.post('/api/v0.1/RU/Config/RuController/set_channel_mode', {
    mode: 'cached',
    scenario_id: opts.scenarioId,
  });
  // 2. Omniverse 建 SimSession(mode=fast_cached)
  await omniverseApiClient.post('/api/v0.1/RAN/SimSession/SimSessionController/create', {
    session_uuid: opts.sessionUuid,
    scene_id: opts.sceneId,
    mode: 'fast_cached',
    scenario_id: opts.scenarioId,
    time_compression_ratio: opts.timeCompressionRatio,
  });
  // 3. DU tick interval 設成 wall_tick = sim_dt / ratio (e.g. 500/2 = 250ms)
  //    CU + e2adapter 會 background pull DU 自動同步 KPM 速度(~4s wall 收斂)。
  await duClient.post('/api/v0.1/DU/Tick/TickController/set_speed', {
    tick_ms: opts.targetWallTickMs,
  });
  // 4. DU tick 起來
  await duClient.post('/api/v0.1/DU/Tick/TickController/start', {});
  // 5. UE scenario driver 起來推位置 + traffic
  await ueClient.post('/api/v0.1/UE/Scenario/ScenarioController/start', {
    scenario_id: opts.scenarioId,
    target_wall_tick_ms: opts.targetWallTickMs,
  });
};

export const stopFastRun = async () => {
  // 倒序:UE driver 停 → DU stop → RU 切回 live
  // KPM 速度不用手動還原 — CU/adapter 會自動跟 DU(stop 後 DU sim_speed_x 不變,
  // 但 indication producer 沒新 measurement 進來,實際 throughput 自然降下)。
  try { await ueClient.post('/api/v0.1/UE/Scenario/ScenarioController/stop', {}); } catch {}
  try { await duClient.post('/api/v0.1/DU/Tick/TickController/stop', {}); } catch {}
  try {
    await ruClient.post('/api/v0.1/RU/Config/RuController/set_channel_mode', { mode: 'live' });
  } catch {}
};
