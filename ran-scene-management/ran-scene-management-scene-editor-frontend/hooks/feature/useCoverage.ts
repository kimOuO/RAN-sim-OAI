'use client';
import { useState } from 'react';
import { computeCoverage, type CoverageResult } from '@/services/api/scenes';

export type CoverageMode = 'rsrp' | 'sinr' | 'cell';

/** 覆蓋熱圖:計算(physics 暫時 engine)+ 顯示選項;結果只存在頁面記憶體 */
export function useCoverage(sceneUuid: string) {
  const [result, setResult] = useState<CoverageResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<CoverageMode>('sinr');
  const [height, setHeight] = useState(1.5);
  const [step, setStep] = useState<number | null>(null);
  const [margin, setMargin] = useState(5);   // 範圍外擴:掃描模型尺寸不在 auto 範圍內
  const [opacity, setOpacity] = useState(0.75);
  const [show, setShow] = useState(true);
  const run = async () => {
    setBusy(true); setError(null);
    try { setResult(await computeCoverage(sceneUuid, { sample_height_m: height, step_m: step, margin_m: margin })); setShow(true); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  return { result, busy, error, mode, setMode, height, setHeight, step, setStep, margin, setMargin, opacity, setOpacity, show, setShow, run, clear: () => setResult(null) };
}
export type CoverageState = ReturnType<typeof useCoverage>;
