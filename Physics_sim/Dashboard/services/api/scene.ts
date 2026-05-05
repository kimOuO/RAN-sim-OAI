import { apiClient } from '@/services/clients/httpClient';
import type { SceneConfig, InitSceneResponse } from '@/types';

export const initScene = async (sceneConfig: SceneConfig): Promise<InitSceneResponse> => {
  const payload: any = {
    scene_id: sceneConfig.scene_id || 'default_scene',
  };

  // DB-only mode: only include geometry_source/gnbs if explicitly provided
  // If omitted, backend will fetch from Omniver-RAN DB
  if (sceneConfig.buildings || sceneConfig.ground) {
    payload.geometry_source = {
      type: 'buildings_json',
      ground: sceneConfig.ground,
      buildings: sceneConfig.buildings,
    };
  }

  if (sceneConfig.gnbs) {
    payload.gnbs = sceneConfig.gnbs.map((gnb: any) => ({
      name: gnb.name,
      pci: gnb.pci ?? 0,
      cell_id: gnb.cell_id ?? '16777216',
      position: gnb.position,
      frequency_ghz: gnb.frequency_ghz,
      power_dbm: gnb.power_dbm,
      bandwidth_mhz: gnb.bandwidth_mhz,
    }));
  }

  if (sceneConfig.ues) {
    payload.ues = sceneConfig.ues.map((ue: any) => ({
      name: ue.name,
      qos_5qi: 9,
      role: 1,
    }));
  }

  if (sceneConfig.scene_antenna_config) {
    payload.scene_antenna_config = sceneConfig.scene_antenna_config;
  }

  const response = await apiClient.post<{ data: InitSceneResponse }>(
    '/api/v0.1/RanpSim/Scene/SceneGateway/init',
    payload
  );
  return response.data.data;
};
