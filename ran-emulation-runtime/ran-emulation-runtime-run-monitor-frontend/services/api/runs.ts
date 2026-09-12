import { DU_API, E2ADAPTER_API, REGISTRY_API } from '@/config';
import { post } from '@/services/clients/apiClient';
import type { DuTick, E2AdapterStatus, Scene, SceneRun } from '@/types/telemetry';

export const listRuns = () => post<SceneRun[]>(`${REGISTRY_API}/Simulation_run/SceneRunReader/read`, {});
export const getRun = (scene_run_uuid: string) => post<SceneRun>(`${REGISTRY_API}/Simulation_run/SceneRunReader/read`, { scene_run_uuid });
export const listScenes = () => post<Scene[]>(`${REGISTRY_API}/Scene_layout/SceneReader/read`, {});
export const getDuTick = () => post<DuTick>(`${DU_API}/Tick/TickController/read`, {}, { timeoutMs: 5000 });
export const getE2AdapterStatus = () => post<E2AdapterStatus>(`${E2ADAPTER_API}/Status/AdapterStatusReader/read`, {}, { timeoutMs: 5000 });
