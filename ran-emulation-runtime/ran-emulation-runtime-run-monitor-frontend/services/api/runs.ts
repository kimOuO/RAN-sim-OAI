import { DU_API, E2ADAPTER_API, ORCHESTRATOR_API, REGISTRY_API, RUNTIME_HOST, UE_API } from '@/config';
import { post } from '@/services/clients/apiClient';
import type { DuCell, DuTick, E2AdapterStatus, RicObservation, RunInstance, Scene, SceneRun, SceneTreeLite, UeDriverStatus } from '@/types/telemetry';
/** RIC 端觀測(閘道 GET 兩趟,慢;獨立慢輪詢) */
export const getRicObservation = (scene_run_uuid: string) => post<RicObservation>(`${ORCHESTRATOR_API}/Run_lifecycle/RicObservationReader/read`, { scene_run_uuid }, { timeoutMs: 20000 });

export const listRuns = () => post<SceneRun[]>(`${REGISTRY_API}/Simulation_run/SceneRunReader/read`, {});
export const getRun = (scene_run_uuid: string) => post<SceneRun>(`${REGISTRY_API}/Simulation_run/SceneRunReader/read`, { scene_run_uuid });
export const listScenes = () => post<Scene[]>(`${REGISTRY_API}/Field_scene/SceneReader/read`, {});
/** per-run 容器(P4-1):registry run_instance 有 host_port 就打該容器;沒有(舊共用模式)就打預設 DU/UE */
export const listRunInstances = (scene_run_uuid: string) => post<RunInstance[]>(`${REGISTRY_API}/Simulation_run/RunInstanceReader/read`, { f_scene_run_uuid: scene_run_uuid });
export const runtimeBase = (inst: RunInstance | undefined, fallback: string, system: 'DU' | 'UE' | 'E2Adapter') => (inst?.host_port ? `http://${RUNTIME_HOST}:${inst.host_port}/api/v0.1/${system}` : fallback);
export const getDuTick = (base: string = DU_API) => post<DuTick>(`${base}/Tick/TickController/read`, {}, { timeoutMs: 5000 });
export const listDuCells = (base: string = DU_API) => post<DuCell[]>(`${base}/MAC/MacCellController/read`, {}, { timeoutMs: 5000 });
export const getUeDriverStatus = (base: string = UE_API) => post<UeDriverStatus>(`${base}/Scenario/ScenarioController/status`, {}, { timeoutMs: 5000 });
export const getE2AdapterStatus = (base: string = E2ADAPTER_API) => post<E2AdapterStatus>(`${base}/Status/AdapterStatusReader/read`, {}, { timeoutMs: 5000 });
export const getSceneTree = (scene_uuid: string) => post<SceneTreeLite>(`${REGISTRY_API}/Field_scene/SceneReader/read_full_tree`, { scene_uuid });
