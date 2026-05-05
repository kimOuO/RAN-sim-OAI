import { apiClient } from '@/services/clients/httpClient';
import type { SetupUERequest, SimStatus } from '@/types';

export const setupUE = async (ueTrajectories: SetupUERequest['ues']): Promise<void> => {
  // 只發送有有效軌跡的 UE（至少 2 個 waypoint）
  const validUEs = ueTrajectories.filter(ue => ue.waypoints && ue.waypoints.length >= 2);

  await apiClient.post('/api/v0.1/RanpSim/RanSignal/SimLoop/setup', {
    ues: validUEs,
  });
};

export const startSim = async (): Promise<void> => {
  await apiClient.post('/api/v0.1/RanpSim/RanSignal/SimLoop/start', {});
};

export const stopSim = async (): Promise<void> => {
  await apiClient.post('/api/v0.1/RanpSim/RanSignal/SimLoop/stop', {});
};

export const getStatus = async (): Promise<SimStatus> => {
  const response = await apiClient.post<{ data: SimStatus }>(
    '/api/v0.1/RanpSim/RanSignal/SimLoop/status',
    {}
  );
  return response.data.data;
};

export const fetchUEPositions = async (): Promise<Record<string, [number, number, number]>> => {
  const response = await apiClient.post<{ data: Record<string, [number, number, number]> }>(
    '/api/v0.1/RanpSim/RanSignal/SimLoop/ue_positions',
    {}
  );
  return response.data.data || {};
};
