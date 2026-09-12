'use client';

/**
 * SimProvider — 把 sim state + unifiedLoop 提到 layout 層級
 * 切 page (/editor → /logs → /playback) 不會 unmount，sim 持續跑。
 *
 * 用法：在 app/layout.tsx 把 children 包起來，
 * 任何 page 都用 useSimContext() 拿 simRunning/signalData/chartData/start/stop。
 */
import { createContext, useContext, useState, ReactNode } from 'react';
import { useSimPage, ChartData } from '@/hooks/feature/useSimPage';
import type { UESignalData } from '@/types';

interface SimContextValue {
  simRunning: boolean;
  signalData: UESignalData[];
  chartData: ChartData[];
  handleStartSim: () => Promise<void>;
  handleStopSim: () => Promise<void>;
  uePositions: Record<string, [number, number, number]>;
  setCoverageLoading: (b: boolean) => void;
  coverageLoading: boolean;
}

const SimContext = createContext<SimContextValue | null>(null);


export function SimProvider({ children }: { children: ReactNode }) {
  const [coverageLoading, setCoverageLoading] = useState(false);
  const [uePositions, setUePositions] = useState<Record<string, [number, number, number]>>({});

  const { simRunning, signalData, chartData, handleStartSim, handleStopSim } = useSimPage({
    onUpdateUEPositions: setUePositions,
    paused: coverageLoading,
  });

  return (
    <SimContext.Provider value={{
      simRunning, signalData, chartData,
      handleStartSim, handleStopSim,
      uePositions,
      setCoverageLoading, coverageLoading,
    }}>
      {children}
    </SimContext.Provider>
  );
}


export function useSimContext(): SimContextValue {
  const ctx = useContext(SimContext);
  if (!ctx) {
    throw new Error('useSimContext must be used inside <SimProvider>');
  }
  return ctx;
}
