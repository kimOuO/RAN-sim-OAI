import { ORCHESTRATOR_API } from '@/config';
import { post } from '@/services/clients/apiClient';
import type { ControlEvent, HandoverEvent, KpmSample, LaunchRequest } from '@/types/telemetry';

const A = `${ORCHESTRATOR_API}/Run_telemetry_archive`;
/** 封存表以 f_scene_run_uuid 過濾;只做排序與預設值,不做呈現決策 */
export const listKpmSamples = async (run: string) =>
  (await post<KpmSample[]>(`${A}/RunKpmSampleReader/read`, { f_scene_run_uuid: run })).sort((a, b) => a.run_kpm_sample_created_at.localeCompare(b.run_kpm_sample_created_at) || a.window_index - b.window_index);
export const listHandoverEvents = async (run: string) => (await post<HandoverEvent[]>(`${A}/RunHandoverEventReader/read`, { f_scene_run_uuid: run })).map((e) => ({ ...e, detail: e.detail ?? {} }));
export const listControlEvents = async (run: string) => (await post<ControlEvent[]>(`${A}/RunControlEventReader/read`, { f_scene_run_uuid: run })).map((e) => ({ ...e, detail: e.detail ?? {} }));
export const listLaunchRequests = (run: string) => post<LaunchRequest[]>(`${ORCHESTRATOR_API}/Run_lifecycle/LaunchRequestReader/read`, { f_scene_run_uuid: run });
