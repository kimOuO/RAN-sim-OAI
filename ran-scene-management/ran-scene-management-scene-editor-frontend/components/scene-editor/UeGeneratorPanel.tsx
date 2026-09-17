'use client';
import { useEffect, useMemo, useState } from 'react';
import { UE_GEN_DEFAULT, UE_SCENARIOS, type UeGenParams } from '@/config';
import type { Extent } from '@/hooks/feature/sceneGeometry';

interface Props { extent: Extent; saving: boolean; ueCount: number; onGenerate: (p: UeGenParams, replace: boolean) => void; onClear: (prefix: string) => void; }
type NumKey = Exclude<keyof UeGenParams, 'namePrefix'>;
const FIELDS: { k: NumKey; l: string; step?: number }[][] = [
  [{ k: 'seed', l: '隨機種子' }, { k: 'count', l: 'UE 數' }, { k: 'duration', l: '長度 s' }],
  [{ k: 'speedMin', l: '速度下限', step: 0.1 }, { k: 'speedMax', l: '速度上限', step: 0.1 }, { k: 'dwellMax', l: '停留上限 s' }],
  [{ k: 'dlMin', l: '輕量 DL kbps' }, { k: 'dlMax', l: '到' }, { k: 'heavyRatio', l: '重度比例', step: 0.05 }],
  [{ k: 'heavyMin', l: '重度 DL kbps' }, { k: 'heavyMax', l: '到' }, { k: 'trafficStep', l: '換流量 s' }],
  [{ k: 'ulMin', l: 'UL kbps' }, { k: 'ulMax', l: '到' }, { k: 'qos5qi', l: '5QI' }],
  [{ k: 'xMin', l: 'x 下限', step: 0.1 }, { k: 'xMax', l: 'x 上限', step: 0.1 }, { k: 'height', l: '天線高 m', step: 0.1 }],
  [{ k: 'zMin', l: 'z 下限', step: 0.1 }, { k: 'zMax', l: 'z 上限', step: 0.1 }],
];
/** 步驟 3:情境範本 + 隨機種子產生 UE(同一個種子永遠得到同一組路徑與流量) */
export function UeGeneratorPanel({ extent, saving, ueCount, onGenerate, onClear }: Props) {
  const base = useMemo(() => ({ ...UE_GEN_DEFAULT, ...extent }), [extent]);
  const [p, setP] = useState<UeGenParams>(base);
  const [scn, setScn] = useState('walk');
  useEffect(() => setP((o) => ({ ...o, ...extent })), [extent.xMin, extent.xMax, extent.zMin, extent.zMax]);   // eslint-disable-line react-hooks/exhaustive-deps
  const applyScenario = (k: string) => { setScn(k); const s = UE_SCENARIOS.find((x) => x.key === k); setP({ ...base, ...s?.params, seed: p.seed }); };
  const set = (k: NumKey, v: string) => setP({ ...p, [k]: Number(v) });
  return (
    <div className="uegen">
      <div className="row head">隨機產生 UE</div>
      <div className="chips">{UE_SCENARIOS.map((s) => <button key={s.key} className={`chip ${scn === s.key ? 'on' : ''}`} title={s.hint} onClick={() => applyScenario(s.key)}>{s.label}</button>)}</div>
      {FIELDS.map((row, i) => <div key={i} className="xyz">{row.map((f) => <label key={f.k} className="stack"><span>{f.l}</span><input type="number" step={f.step ?? 1} value={p[f.k]} onChange={(e) => set(f.k, e.target.value)} /></label>)}</div>)}
      <label className="stack"><span>名稱前綴</span><input value={p.namePrefix} onChange={(e) => setP({ ...p, namePrefix: e.target.value || 'u' })} /></label>
      <div className="actions">
        <button className="primary" disabled={saving || p.count < 1} onClick={() => onGenerate(p, true)} title="同前綴的舊 UE 會先刪掉">產生(取代 {p.namePrefix}*)</button>
        <button disabled={saving || p.count < 1} onClick={() => onGenerate({ ...p, namePrefix: `${p.namePrefix}${Date.now() % 1000}_` }, false)}>追加一批</button>
        <button className="ghost danger" disabled={saving || !ueCount} onClick={() => { if (confirm(`刪除所有名稱以「${p.namePrefix}」開頭的 UE?`)) onClear(p.namePrefix); }}>清除 {p.namePrefix}*</button>
        <button className="ghost" onClick={() => setP({ ...p, seed: Math.floor(Math.random() * 1e6) })}>換種子</button>
      </div>
      <p className="muted small">範圍預設取場景外框(建築 / gNB / 既有路徑)。同一個種子會產生相同結果,可用來做重現的對照實驗。</p>
    </div>
  );
}
