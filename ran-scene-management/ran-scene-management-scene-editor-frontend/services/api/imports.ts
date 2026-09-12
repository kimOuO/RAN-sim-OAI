import { REGISTRY_API } from '@/config';
import { post } from '@/services/clients/apiClient';

export const importScenarioV1 = (raw_json: unknown) => post<{ scene_uuid: string; scene_run_uuid: string }>(`${REGISTRY_API}/Scene_layout/ScenarioImporter/import_v1`, { raw_json });
