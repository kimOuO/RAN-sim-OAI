import { REGISTRY_API } from '@/config';
import { post } from '@/services/clients/apiClient';
import type { AntennaPreset, DuConfigTemplate, Material } from '@/types/registry';

const P = `${REGISTRY_API}/Preset_catalog`;
export const listAntennaPresets = () => post<AntennaPreset[]>(`${P}/AntennaPresetReader/read`, {});
export const listMaterials = () => post<Material[]>(`${P}/MaterialReader/read`, {});
export const listDuConfigTemplates = () => post<DuConfigTemplate[]>(`${P}/DuConfigTemplateReader/read`, {});
export const createAntennaPreset = (body: Partial<AntennaPreset>) => post<AntennaPreset>(`${P}/AntennaPresetController/create`, body);
