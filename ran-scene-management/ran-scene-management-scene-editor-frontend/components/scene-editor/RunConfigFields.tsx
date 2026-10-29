'use client';
import { useEffect, useState } from 'react';
import type { SceneRun } from '@/types/registry';

export function RunConfigFields({ run, saving, onSave }: { run: SceneRun | null; saving: boolean; onSave: (f: Partial<SceneRun>) => void }) {
  const [mode, setMode] = useState<SceneRun['mode']>(run?.mode ?? 'live');
  const [speed, setSpeed] = useState(String(run?.speed_x ?? 1));
  const [dt, setDt] = useState(String(run?.sim_dt_ms ?? 500));
  const [duration, setDuration] = useState(String(run?.duration_sec ?? 3600));
  useEffect(() => {
    setMode(run?.mode ?? 'live'); setSpeed(String(run?.speed_x ?? 1));
    setDt(String(run?.sim_dt_ms ?? 500)); setDuration(String(run?.duration_sec ?? 3600));
  }, [run?.scene_run_uuid, run?.mode, run?.speed_x, run?.sim_dt_ms, run?.duration_sec]);
  const locked = saving || run?.status === 'running' || run?.status === 'precomputing';
  const valid = Number(speed) > 0 && Number.isFinite(Number(speed)) && Number.isInteger(Number(dt)) && Number(dt) >= 10 && Number(dt) <= 500
    && Number.isInteger(Number(duration)) && Number(duration) > 0;
  return <>
    <div className="row head">Run 設定 <span className="muted">{run?.status ?? '尚無 run'}</span></div>
    <label><span>模式</span><select disabled={locked} value={mode} onChange={(e) => setMode(e.target.value as SceneRun['mode'])}><option value="live">live(Sionna 即時)</option><option value="cached">cached(預算 npz)</option></select></label>
    <label><span>倍速</span><input disabled={locked} type="number" step="any" min={0.01} value={speed} onChange={(e) => setSpeed(e.target.value)} /></label>
    <label><span>sim_dt ms (10–500)</span><input disabled={locked} type="number" min={10} max={500} value={dt} onChange={(e) => setDt(e.target.value)} /></label>
    <label><span>時長 s</span><input disabled={locked} type="number" min={1} value={duration} onChange={(e) => setDuration(e.target.value)} /></label>
    {!valid && <p className="err small">倍速與時長須大於 0；步長為 10–500 ms 的整數。</p>}
    <p className="muted small">{locked ? '執行或預算中，請先停止再修改啟動設定。' : '修改後按儲存設定；變更路徑、場景或預算設定後，cached 模式需重新預算。'}</p>
    <div className="actions"><button className="primary" disabled={locked || !valid}
      onClick={() => onSave({ mode, speed_x: Number(speed), sim_dt_ms: Number(dt), duration_sec: Number(duration) })}>{run ? '儲存 Run 設定' : '建立 Run 設定'}</button></div>
  </>;
}
