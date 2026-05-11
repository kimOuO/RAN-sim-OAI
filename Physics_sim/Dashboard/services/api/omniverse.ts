import axios from 'axios';
import { apiClient } from '@/services/clients/httpClient';
import { OMNIVERSE_API_URL } from '@/config';
import type { UsdAsset, Building, SceneLayout } from '@/types';

export const omniverseApiClient = axios.create({
  baseURL: OMNIVERSE_API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ─── Assets ─────────────────────────────────────────────────────

export const listAssets = async (objectType?: string): Promise<UsdAsset[]> => {
  const response = await omniverseApiClient.post<{ data: UsdAsset[] }>(
    '/api/v0.1/RAN/Assets/UsdAssetReader/list',
    { object_type: objectType }
  );
  return response.data.data || [];
};

export const createAsset = async (data: Partial<UsdAsset>): Promise<UsdAsset> => {
  const response = await omniverseApiClient.post<{ data: UsdAsset }>(
    '/api/v0.1/RAN/Assets/UsdAssetController/create',
    data
  );
  return response.data.data;
};

export const updateAsset = async (
  presetId: string,
  data: Partial<UsdAsset>
): Promise<UsdAsset> => {
  const response = await omniverseApiClient.post<{ data: UsdAsset }>(
    '/api/v0.1/RAN/Assets/UsdAssetController/update',
    { preset_id: presetId, ...data }
  );
  return response.data.data;
};

export const deleteAsset = async (presetId: string): Promise<void> => {
  await omniverseApiClient.post('/api/v0.1/RAN/Assets/UsdAssetController/delete', {
    preset_id: presetId,
  });
};

// ─── Buildings ──────────────────────────────────────────────────

export const listBuildings = async (): Promise<Building[]> => {
  try {
    const response = await omniverseApiClient.post<{ data: Building[] }>(
      '/api/v0.1/RAN/Scene/BuildingController/read',
      {}
    );
    return response.data.data || [];
  } catch (error) {
    console.warn('Failed to list buildings, returning empty list:', error);
    return [];
  }
};

export const createBuilding = async (data: Partial<Building>): Promise<Building> => {
  const response = await omniverseApiClient.post<{ data: Building }>(
    '/api/v0.1/RAN/Scene/BuildingController/create',
    data
  );
  return response.data.data;
};

export const updateBuilding = async (
  name: string,
  data: Partial<Building>
): Promise<Building> => {
  const response = await omniverseApiClient.post<{ data: Building }>(
    '/api/v0.1/RAN/Scene/BuildingController/update',
    { name, ...data }
  );
  return response.data.data;
};

export const deleteBuilding = async (name: string): Promise<void> => {
  try {
    await omniverseApiClient.post('/api/v0.1/RAN/Scene/BuildingController/delete', {
      name,
    });
  } catch (error: any) {
    if (error.response?.status === 404) {
      console.warn(`Building '${name}' not found in database, skipping delete`);
      return;
    }
    throw error;
  }
};

// ─── GNBs ───────────────────────────────────────────────────────

export const listGnbs = async (): Promise<any[]> => {
  try {
    const response = await omniverseApiClient.post<{ data: any[] }>(
      '/api/v0.1/RAN/GNB/GNBReader/read',
      {}
    );
    return response.data.data || [];
  } catch (error) {
    console.warn('Failed to list GNBs, returning empty list:', error);
    return [];
  }
};

export const createGnb = async (data: any): Promise<any> => {
  const response = await omniverseApiClient.post<{ data: any }>(
    '/api/v0.1/RAN/GNB/GNBController/create',
    data
  );
  return response.data.data;
};

export const deleteGnb = async (name: string): Promise<void> => {
  try {
    await omniverseApiClient.post('/api/v0.1/RAN/GNB/GNBController/delete', {
      name,
    });
  } catch (error: any) {
    if (error.response?.status === 404) {
      console.warn(`gNB '${name}' not found in database, skipping delete`);
      return;
    }
    throw error;
  }
};

// ─── UEs ────────────────────────────────────────────────────────

export const listUes = async (): Promise<any[]> => {
  try {
    const response = await omniverseApiClient.post<{ data: any[] }>(
      '/api/v0.1/RAN/UE/UEReader/read',
      {}
    );
    return response.data.data || [];
  } catch (error) {
    console.warn('Failed to list UEs, returning empty list:', error);
    return [];
  }
};

export const createUe = async (data: any): Promise<any> => {
  const response = await omniverseApiClient.post<{ data: any }>(
    '/api/v0.1/RAN/UE/UEController/create',
    data
  );
  return response.data.data;
};

export const deleteUe = async (name: string): Promise<void> => {
  try {
    await omniverseApiClient.post('/api/v0.1/RAN/UE/UEController/delete', {
      name,
    });
  } catch (error: any) {
    if (error.response?.status === 404) {
      console.warn(`UE '${name}' not found in database, skipping delete`);
      return;
    }
    throw error;
  }
};

export const updateUe = async (name: string, data: any): Promise<any> => {
  const response = await omniverseApiClient.post<{ data: any }>(
    '/api/v0.1/RAN/UE/UEController/update',
    { name, ...data }
  );
  return response.data.data;
};

// ─── Obstacles ──────────────────────────────────────────────────

export const listObstacles = async (): Promise<any[]> => {
  try {
    const response = await omniverseApiClient.post<{ data: any[] }>(
      '/api/v0.1/RAN/Scene/ObstacleController/read',
      {}
    );
    return response.data.data || [];
  } catch (error) {
    console.warn('Failed to list obstacles, returning empty list:', error);
    return [];
  }
};

export const createObstacle = async (data: any): Promise<any> => {
  const response = await omniverseApiClient.post<{ data: any }>(
    '/api/v0.1/RAN/Scene/ObstacleController/create',
    data
  );
  return response.data.data;
};

export const deleteObstacle = async (name: string): Promise<void> => {
  try {
    await omniverseApiClient.post('/api/v0.1/RAN/Scene/ObstacleController/delete', {
      name,
    });
  } catch (error: any) {
    if (error.response?.status === 404) {
      console.warn(`Obstacle '${name}' not found in database, skipping delete`);
      return;
    }
    throw error;
  }
};

// ─── Scene Control ──────────────────────────────────────────────

export const getSceneLayout = async (): Promise<SceneLayout> => {
  try {
    console.log('%c[omniverseApi] 正在調用 SceneLayoutReader/read', 'color: #0066cc; font-weight: bold');
    console.log('%c目標: http://localhost:8001/api/v0.1/RAN/Scene/SceneLayoutReader/read', 'color: #0066cc');
    const response = await omniverseApiClient.post<{ data: SceneLayout }>(
      '/api/v0.1/RAN/Scene/SceneLayoutReader/read',
      {}
    );
    const sceneData = response.data.data;
    console.log('%c✓ API 返回成功', 'color: #00aa00; font-weight: bold');
    console.log('Buildings 數量:', sceneData.buildings?.length);
    console.log('gNBs 數量:', sceneData.gnbs?.length);
    console.log('UEs 數量:', sceneData.ues?.length);
    console.log('完整響應:', sceneData);
    return sceneData;
  } catch (error) {
    console.error('[omniverseApi] Error calling SceneLayoutReader:', error);
    throw error;
  }
};

export const buildScene = async (): Promise<void> => {
  await omniverseApiClient.post('/api/v0.1/RAN/Scene/SceneController/build', {});
};

// ─── Kit Animation Control ──────────────────────────────────────

export const startAnimation = async (): Promise<void> => {
  await omniverseApiClient.post('/api/v0.1/RAN/Scene/AnimationController/start', {});
};

export const stopAnimation = async (): Promise<void> => {
  await omniverseApiClient.post('/api/v0.1/RAN/Scene/AnimationController/stop', {});
};

export const clearScene = async (): Promise<void> => {
  try {
    console.log('%c[omniverseApi] 正在調用 SceneController/clear', 'color: #ff0000; font-weight: bold');
    console.log('%c目標: http://localhost:8001/api/v0.1/RAN/Scene/SceneController/clear', 'color: #ff0000');
    const response = await omniverseApiClient.post('/api/v0.1/RAN/Scene/SceneController/clear', {});
    console.log('%c✓ Clear 命令已發送到後端', 'color: #00aa00; font-weight: bold');
    console.log('響應:', response.data);
  } catch (error) {
    console.error('%c✗ Clear Scene 失敗', 'color: #ff0000; font-weight: bold', error);
    throw error;
  }
};

// ─── UE Trajectory ──────────────────────────────────────────────

export const setUeTrajectory = async (
  name: string,
  waypoints: Array<[number, number, number]>,
  speed_mps: number,
  loop: boolean = true
): Promise<void> => {
  await omniverseApiClient.post('/api/v0.1/RAN/UE/UEController/trajectory', {
    name,
    waypoints,
    speed_mps,
    loop,
  });
};

// ─── gNB Update ─────────────────────────────────────────────────

export const updateGnb = async (name: string, data: any): Promise<any> => {
  const response = await omniverseApiClient.post<{ data: any }>(
    '/api/v0.1/RAN/GNB/GNBController/update',
    { name, ...data }
  );
  return response.data.data;
};

// ─── 3D Replay: Scene Snapshot ──────────────────────────────────

export const ingestScene = async (sceneId: string, snapshot: any): Promise<void> => {
  // Push snapshot directly to Kit without modifying DB (for Playback)
  await omniverseApiClient.post('/api/v0.1/RAN/Scene/SceneController/push_snapshot_to_kit', {
    config: {
      scene_id: sceneId,
      buildings: snapshot.buildings || [],
      gnbs: snapshot.gnbs || [],
      ues: snapshot.ues || [],
      ground: snapshot.ground,
    },
  });
};

// ─── 3D Replay: Batch Move UEs ──────────────────────────────────

export const batchMoveUEs = async (
  ues: Array<{ name: string; x: number; y: number; z: number; rsrp_dbm?: number; sinr_db?: number; serving_cell?: string; serving_gnb?: string; serving_pci?: number; serving_cell_id?: string }>
): Promise<void> => {
  if (ues.length === 0) return;
  await omniverseApiClient.post('/api/v0.1/RAN/UE/UEController/batch_move', { ues });
};
