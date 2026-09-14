import { ORCHESTRATOR_API, REGISTRY_API } from '@/config';
import { post } from '@/services/clients/apiClient';
import type { RunKnob, SceneRun } from '@/types/registry';

const S = `${REGISTRY_API}/Simulation_run`;
export const listSceneRuns = (f_scene_uuid?: string) => post<SceneRun[]>(`${S}/SceneRunReader/read`, f_scene_uuid ? { f_scene_uuid } : {});
export const createSceneRun = (body: Partial<SceneRun> & { f_scene_uuid: string }) => post<SceneRun>(`${S}/SceneRunController/create`, body);
export const updateSceneRun = (scene_run_uuid: string, body: Partial<SceneRun>) => post<SceneRun>(`${S}/SceneRunController/update`, { scene_run_uuid, ...body });
export const listRunKnobs = (f_scene_run_uuid: string) => post<RunKnob[]>(`${S}/RunKnobReader/read`, { f_scene_run_uuid });
export const createRunKnob = (body: { f_scene_run_uuid: string; key: string; value: unknown }) => post<RunKnob>(`${S}/RunKnobController/create`, body);
export const updateRunKnob = (run_knob_uuid: string, value: unknown) => post<RunKnob>(`${S}/RunKnobController/update`, { run_knob_uuid, value });
export const deleteRunKnob = (run_knob_uuid: string) => post<{ deleted: number }>(`${S}/RunKnobController/delete`, { run_knob_uuid });
export const startRun = (scene_run_uuid: string, speed_x?: number, sim_dt_ms?: number) =>
  post<{ scene_run_uuid: string }>(`${ORCHESTRATOR_API}/Run_lifecycle/LaunchController/start`, { scene_run_uuid, speed_x, sim_dt_ms }, { timeoutMs: 200_000 });
export const stopRun = (scene_run_uuid: string) => post<{ scene_run_uuid: string }>(`${ORCHESTRATOR_API}/Run_lifecycle/LaunchController/stop`, { scene_run_uuid }, { timeoutMs: 200_000 });
export interface PrecomputeStatus { state: string; exit_code: number | null; done: boolean; progress: { tick: number; total: number; pct: number; rate_tps: number; eta_sec: number } | null; scenario_id?: string; last_lines?: string[]; }
export const precomputeRun = (scene_run_uuid: string) => post<{ scene_run_uuid: string }>(`${ORCHESTRATOR_API}/Run_lifecycle/PrecomputeController/start`, { scene_run_uuid }, { timeoutMs: 60_000 });
export const stopPrecompute = (scene_run_uuid: string) => post<{ scene_run_uuid: string }>(`${ORCHESTRATOR_API}/Run_lifecycle/PrecomputeController/stop`, { scene_run_uuid });
export const readPrecompute = (scene_run_uuid: string) => post<PrecomputeStatus>(`${ORCHESTRATOR_API}/Run_lifecycle/PrecomputeReader/read`, { scene_run_uuid }, { timeoutMs: 10_000 });
