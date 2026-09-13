import { DU_API, E2ADAPTER_API, REGISTRY_API, UE_API } from '@/config';
import { post } from '@/services/clients/apiClient';
import type { DuCell, DuTick, E2AdapterStatus, Scene, SceneRun, UeDriverStatus } from '@/types/telemetry';

export const listRuns = () => post<SceneRun[]>(`${REGISTRY_API}/Simulation_run/SceneRunReader/read`, {});
export const getRun = (scene_run_uuid: string) => post<SceneRun>(`${REGISTRY_API}/Simulation_run/SceneRunReader/read`, { scene_run_uuid });
export const listScenes = () => post<Scene[]>(`${REGISTRY_API}/Scene_layout/SceneReader/read`, {});
/** 執行中服務的狀態(P4 之後改成依 run 的容器讀;現在是全域單一 DU/UE) */
export const getDuTick = () => post<DuTick>(`${DU_API}/Tick/TickController/read`, {}, { timeoutMs: 5000 });
export const listDuCells = () => post<DuCell[]>(`${DU_API}/MAC/MacCellController/read`, {}, { timeoutMs: 5000 });
export const getUeDriverStatus = () => post<UeDriverStatus>(`${UE_API}/Scenario/ScenarioController/status`, {}, { timeoutMs: 5000 });
export const getE2AdapterStatus = () => post<E2AdapterStatus>(`${E2ADAPTER_API}/Status/AdapterStatusReader/read`, {}, { timeoutMs: 5000 });
