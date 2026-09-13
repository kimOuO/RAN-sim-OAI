'use client';
import { RANGE_OPTIONS } from '@/config';
export function RangeBar({ range, setRange, live, windows }: { range: number; setRange: (n: number) => void; live: boolean; windows: number }) {
  return (
    <div className="rangebar">{RANGE_OPTIONS.map((o) => <button key={o.label} className={`chip ${range === o.windows ? 'on' : ''}`} onClick={() => setRange(o.windows)}>{o.label}</button>)}
      <span className="muted">{windows} 視窗</span>{live && <span className="live"><i />LIVE · 3 s</span>}</div>
  );
}
