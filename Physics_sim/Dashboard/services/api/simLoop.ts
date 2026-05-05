// 4-system 拆分後：tick driver / sim 控制權限轉移到 DU
// 舊 path /api/v0.1/RanpSim/RanSignal/SimLoop/* → 新 /api/v0.1/DU/Tick/TickController/*
import { duClient } from '@/services/clients/httpClient';
import type { SetupUERequest, SimStatus } from '@/types';

export const setupUE = async (ueTrajectories: SetupUERequest['ues']): Promise<void> => {
  // 只發送有有效軌跡的 UE（至少 2 個 waypoint）
  const validUEs = ueTrajectories.filter(ue => ue.waypoints && ue.waypoints.length >= 2);

  // DU 用 register_ue 取代舊的 SimLoop/setup
  for (const ue of validUEs) {
    await duClient.post('/api/v0.1/DU/Tick/TickController/register_ue', ue);
  }
};

export const startSim = async (): Promise<void> => {
  await duClient.post('/api/v0.1/DU/Tick/TickController/start', {});
};

export const stopSim = async (): Promise<void> => {
  await duClient.post('/api/v0.1/DU/Tick/TickController/stop', {});
};

export const getStatus = async (): Promise<SimStatus> => {
  const response = await duClient.post<{ data: SimStatus }>(
    '/api/v0.1/DU/Tick/TickController/read',
    {}
  );
  return response.data.data;
};

export const fetchUEPositions = async (): Promise<Record<string, [number, number, number]>> => {
  // TickController/read 回傳的 status 應含 ue_positions 子欄位（DU side 已實作）
  const response = await duClient.post<{ data: SimStatus & { ue_positions?: Record<string, [number, number, number]> } }>(
    '/api/v0.1/DU/Tick/TickController/read',
    {}
  );
  return response.data.data?.ue_positions || {};
};
