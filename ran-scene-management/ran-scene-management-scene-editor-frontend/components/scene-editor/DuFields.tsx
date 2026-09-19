'use client';
import { useEffect, useState } from 'react';
import { SCHEDULERS } from '@/config';
import type { Du } from '@/types/registry';

type Num = 'numerology' | 'n_prb' | 'min_prb' | 'pf_alpha' | 'target_bler' | 'rlc_discard_timer_ms' | 'harq_max_retx';
const NUM: { k: Num; label: string; step?: number; hint?: string }[] = [
  { k: 'n_prb', label: 'PRB 數', hint: '40 MHz ≈ 106' },
  { k: 'min_prb', label: '每 UE 最少 PRB' },
  { k: 'numerology', label: 'numerology', hint: '1 = 30 kHz' },
  { k: 'pf_alpha', label: 'PF α', step: 0.01 },
  { k: 'target_bler', label: '目標 BLER', step: 0.01 },
  { k: 'rlc_discard_timer_ms', label: 'discard ms' },
  { k: 'harq_max_retx', label: 'HARQ 重傳上限' },
];

/** DU 執行參數:顯示模板值,改動存成這個 DU 的 config_override(留空 = 沿用模板) */
export function DuFields({ du, saving, onDu }: { du: Du; saving: boolean; onDu: (d: Du, f: Partial<Du>) => void }) {
  const tpl = du.config_template ?? null;
  const ov = (du.config_override ?? {}) as Record<string, unknown>;
  const [f, setF] = useState<Record<string, string>>({});
  useEffect(() => {
    const o = (du.config_override ?? {}) as Record<string, unknown>;
    setF(Object.fromEntries(Object.entries(o).map(([k, v]) => [k, String(v)])));
  }, [du]);
  const set = (k: string, v: string) => setF((x) => ({ ...x, [k]: v }));
  const shown = (k: string) => f[k] ?? '';
  const tplVal = (k: string) => (tpl ? String((tpl as unknown as Record<string, unknown>)[k] ?? '') : '');
  const apply = () => {
    const out: Record<string, unknown> = {};
    for (const { k } of NUM) if (shown(k).trim() !== '') out[k] = Number(shown(k));
    if (shown('tdd_pattern').trim()) out.tdd_pattern = shown('tdd_pattern').trim().toUpperCase();
    if (shown('scheduler')) out.scheduler = shown('scheduler');
    if (shown('qos_gbr_first')) out.qos_gbr_first = shown('qos_gbr_first') === 'on';
    onDu(du, { config_override: Object.keys(out).length ? out : null });
  };
  return (
    <>
      <p className="muted small">下面是這個 DU 的覆寫;留空 = 沿用模板{tpl ? `「${tpl.name}」` : '(服務預設)'}。改完要重啟 run 才生效。</p>
      <label><span>排程器</span>
        <select value={shown('scheduler')} onChange={(e) => set('scheduler', e.target.value)}>
          <option value="">(模板:{SCHEDULERS.find((s) => s.key === tpl?.scheduler)?.label ?? 'PF 比例公平'})</option>
          {SCHEDULERS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select></label>
      <label><span>TDD pattern</span>
        <input value={shown('tdd_pattern')} placeholder={tplVal('tdd_pattern') || 'DDDDDDDSUU'} onChange={(e) => set('tdd_pattern', e.target.value)} /></label>
      {NUM.map(({ k, label, step, hint }) => (
        <label key={k}><span>{label}</span>
          <input type="number" step={step ?? 1} value={shown(k)} placeholder={tplVal(k) || hint || ''} onChange={(e) => set(k, e.target.value)} /></label>))}
      <label><span>GBR 優先</span>
        <select value={shown('qos_gbr_first')} onChange={(e) => set('qos_gbr_first', e.target.value)}>
          <option value="">(模板:{tpl ? (tpl.qos_gbr_first ? '開' : '關') : '開'})</option><option value="on">開</option><option value="off">關</option>
        </select></label>
      <div className="actions">
        <button className="primary" disabled={saving} onClick={apply}>儲存 DU 覆寫</button>
        {Object.keys(ov).length > 0 && <button disabled={saving} onClick={() => { setF({}); onDu(du, { config_override: null }); }}>清除覆寫</button>}
      </div>
    </>
  );
}
