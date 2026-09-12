import { ORCHESTRATOR_API, REGISTRY_API } from '@/config';
import { post } from '@/services/clients/apiClient';
import type { SceneRun } from '@/types/registry';

export const listSceneRuns = (f_scene_uuid?: string) => post<SceneRun[]>(`${REGISTRY_API}/Simulation_run/SceneRunReader/read`, f_scene_uuid ? { f_scene_uuid } : {});
export const createSceneRun = (body: Partial<SceneRun> & { f_scene_uuid: string }) => post<SceneRun>(`${REGISTRY_API}/Simulation_run/SceneRunController/create`, body);
export const startRun = (scene_run_uuid: string, speed_x?: number, sim_dt_ms?: number) =>
  post<{ scene_run_uuid: string }>(`${ORCHESTRATOR_API}/Run_lifecycle/LaunchController/start`, { scene_run_uuid, speed_x, sim_dt_ms }, { timeoutMs: 200_000 });
export const stopRun = (scene_run_uuid: string) => post<{ scene_run_uuid: string }>(`${ORCHESTRATOR_API}/Run_lifecycle/LaunchController/stop`, { scene_run_uuid }, { timeoutMs: 200_000 });
