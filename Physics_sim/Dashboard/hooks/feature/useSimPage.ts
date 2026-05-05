'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { startSim, stopSim, setupUE, fetchUEPositions } from '@/services/api/simLoop';
import { WS_URL, SIM_LOOP_TICK_MS, API_BASE_URL } from '@/config';
import * as omniverseApi from '@/services/api/omniverse';
import type { UESignalData } from '@/types';

export interface ChartData {
  tick: number;
  [ueKey: string]: number | string;
}

interface UseSimPageOptions {
  onUpdateUEPositions?: (positions: Record<string, [number, number, number]>) => void;
}

export function useSimPage(options?: UseSimPageOptions) {
  const router = useRouter();
  const wsRef = useRef<WebSocket | null>(null);
  const positionPollRef = useRef<NodeJS.Timeout | null>(null);
  const [simRunning, setSimRunning] = useState(false);
  const [signalData, setSignalData] = useState<UESignalData[]>([]);
  const [chartData, setChartData] = useState<ChartData[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // 頁面載入時檢查後端 SimLoop 狀態
  useEffect(() => {
    const checkSimStatus = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v0.1/RanpSim/RanSignal/SimLoop/status`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: '{}',
        });
        if (response.ok) {
          const data = await response.json();
          if (data.data?.is_running) {
            setSimRunning(true);
          }
        }
      } catch {
        // 無法查詢狀態，靜默失敗
      }
    };
    checkSimStatus();
  }, []);

  const handleStartSim = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // 從 DB 讀取 UE 配置（含軌跡）
      const uesFromDb = await omniverseApi.listUes();
      if (uesFromDb.length > 0) {
        const uePayload = uesFromDb
          .filter(ue => ue.waypoints && ue.waypoints.length >= 2)
          .map((ue) => ({
            name: ue.name,
            waypoints: ue.waypoints || [],
            speed_mps: ue.speed_mps || 1.0,
            loop: true,
          }));
        if (uePayload.length > 0) {
          await setupUE(uePayload);
        }
      }

      await startSim();
      setSimRunning(true);

      // 輪詢 UE 位置（如果有回調）
      if (options?.onUpdateUEPositions) {
        const pollPositions = async () => {
          try {
            const positions = await fetchUEPositions();
            options.onUpdateUEPositions!(positions);
          } catch {
            console.warn('Failed to fetch UE positions');
          }
        };
        positionPollRef.current = setInterval(pollPositions, SIM_LOOP_TICK_MS);
      }

      // WebSocket 連接為可選（Omniverse 不是必需的）
      try {
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            if (message.type === 'ue_update' && Array.isArray(message.ues)) {
              setSignalData(message.ues);

              setChartData((prev) => {
                const tick = message.tick || prev.length;
                const newDataPoint: ChartData = { tick };
                message.ues.forEach((ue: UESignalData) => {
                  newDataPoint[`${ue.ue_name}_rsrp`] = ue.rsrp_dbm ?? 0;
                  newDataPoint[`${ue.ue_name}_sinr`] = ue.sinr_db ?? 0;
                });
                const updated = [...prev, newDataPoint];
                return updated.slice(-100);
              });
            }
          } catch {
            console.error('Failed to parse WebSocket message');
          }
        };

        ws.onerror = () => {
          console.warn('WebSocket connection failed - continuing with polling');
        };

        ws.onclose = () => {
          wsRef.current = null;
        };
      } catch {
        console.warn('WebSocket unavailable - using polling instead');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start simulation');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleStopSim = useCallback(async () => {
    try {
      setLoading(true);
      // 停止輪詢位置
      if (positionPollRef.current) {
        clearInterval(positionPollRef.current);
        positionPollRef.current = null;
      }
      // 關閉 WebSocket
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      await stopSim();
      setSimRunning(false);
      router.push('/playback');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop simulation');
    } finally {
      setLoading(false);
    }
  }, [router]);

  // 當 simRunning 變 true 時啟動 polling（包含 refresh 後從後端讀到 is_running=true 的情況）
  useEffect(() => {
    if (!simRunning) return;
    if (!options?.onUpdateUEPositions) return;
    if (positionPollRef.current) return; // 已經在 poll，不要重複

    const pollPositions = async () => {
      try {
        const positions = await fetchUEPositions();
        options.onUpdateUEPositions!(positions);
      } catch {
        console.warn('Failed to fetch UE positions');
      }
    };
    pollPositions();
    positionPollRef.current = setInterval(pollPositions, SIM_LOOP_TICK_MS);

    return () => {
      if (positionPollRef.current) {
        clearInterval(positionPollRef.current);
        positionPollRef.current = null;
      }
    };
  }, [simRunning, options?.onUpdateUEPositions]);

  useEffect(() => {
    return () => {
      // 清理前端資源（polling 定時器），但保持 WebSocket 開著
      // 這樣跳頁時不會斷線，其他頁面可以繼續接收信號
      if (positionPollRef.current) {
        clearInterval(positionPollRef.current);
      }
      // 不關 wsRef.current，讓 WebSocket 保持連線
      // 不呼叫 handleStopSim()，以免後端 SimLoop 被中斷
    };
  }, []);

  return {
    simRunning,
    signalData,
    chartData,
    error,
    loading,
    handleStartSim,
    handleStopSim,
  };
}
