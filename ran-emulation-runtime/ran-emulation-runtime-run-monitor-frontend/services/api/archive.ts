import { KPM_FETCH_LIMIT, ORCHESTRATOR_API } from '@/config';
import { post } from '@/services/clients/apiClient';
import type { ControlEvent, HandoverEvent, KpmSample, LaunchRequest } from '@/types/telemetry';

const A = `${ORCHESTRATOR_API}/Run_telemetry_archive`;
/** 封存表以 f_scene_run_uuid 過濾;只做排序與預設值,不做呈現決策 */
export const listKpmSamples = async (run: string, afterId = 0) =>
  (await post<KpmSample[]>(`${A}/RunKpmSampleReader/read`, { f_scene_run_uuid: run, limit: KPM_FETCH_LIMIT, after_id: afterId })).sort((a, b) => a.run_kpm_sample_created_at.localeCompare(b.run_kpm_sample_created_at) || a.window_index - b.window_index);
export const listHandoverEvents = async (run: string, afterId = 0) => (await post<HandoverEvent[]>(`${A}/RunHandoverEventReader/read`, { f_scene_run_uuid: run, after_id: afterId, limit: 5000 })).map((e) => ({ ...e, detail: e.detail ?? {} }));
export const listControlEvents = async (run: string) => (await post<ControlEvent[]>(`${A}/RunControlEventReader/read`, { f_scene_run_uuid: run })).map((e) => ({ ...e, detail: e.detail ?? {} }));
export const listLaunchRequests = (run: string) => post<LaunchRequest[]>(`${ORCHESTRATOR_API}/Run_lifecycle/LaunchRequestReader/read`, { f_scene_run_uuid: run });
/** 最近幾筆 KPM(3D 即時頁 2 s 輪詢用,不能整包拉) */
export const listLatestKpmSamples = async (run: string, n = 4) =>
  (await post<KpmSample[]>(`${A}/RunKpmSampleReader/read`, { f_scene_run_uuid: run, limit: n }, { timeoutMs: 5000 })).sort((a, b) => a.window_index - b.window_index);
