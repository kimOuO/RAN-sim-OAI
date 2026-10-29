'use client';
import { useState } from 'react';
import { useElementWidth } from '@/hooks/base/useElementWidth';

interface Col { label: string; value: number; }
/** 直條(分桶計數:直方圖、每分鐘事件數)。兩組時並排。 */
export function ColumnChart({ groups, height = 160, unit = '' }: { groups: { name: string; color: string; cols: Col[] }[]; height?: number; unit?: string }) {
  const { ref, width } = useElementWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const n = groups[0]?.cols.length ?? 0; if (!n) return <div ref={ref} className="chart empty" style={{ height }}><span className="muted">尚無資料</span></div>;
  const PAD = { l: 30, r: 8, t: 8, b: 22 }; const iw = width - PAD.l - PAD.r, ih = height - PAD.t - PAD.b;
  // 非有限值(NaN / Infinity)當 0,否則最大值變 NaN,刻度文字會渲染成 NaN
  // 計數只能是整數:上限取偶數(至少 2),中間刻度才會是整數,不會出現「1 / 1 / 0」
  const raw = Math.max(...groups.flatMap((g) => g.cols.map((c) => (Number.isFinite(c.value) ? c.value : 0))));
  const hi = Math.max(2, Math.ceil(raw / 2) * 2);
  const slot = iw / n, bw = Math.max(2, (slot - 4) / groups.length - 2);
  const tickEvery = Math.max(1, Math.ceil(n / 8));
  return (
    <div ref={ref} className="chart">
      <svg width={width} height={height} role="img" aria-label="column chart">
        {[0, 0.5, 1].map((f) => <g key={f}><line x1={PAD.l} x2={width - PAD.r} y1={PAD.t + ih * (1 - f)} y2={PAD.t + ih * (1 - f)} className="grid" /><text x={PAD.l - 5} y={PAD.t + ih * (1 - f) + 3.5} textAnchor="end" className="tick">{hi * f}</text></g>)}
        {groups[0].cols.map((c, i) => (
          <g key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <rect x={PAD.l + i * slot} y={PAD.t} width={slot} height={ih} fill="transparent" />
            {groups.map((g, gi) => { const v = Number.isFinite(g.cols[i]?.value) ? g.cols[i].value : 0; const h = (v / hi) * ih; return <rect key={g.name} x={PAD.l + i * slot + 2 + gi * (bw + 2)} y={PAD.t + ih - h} width={bw} height={h} rx="3" fill={g.color} opacity={hover == null || hover === i ? 1 : 0.5} />; })}
            {i % tickEvery === 0 && <text x={PAD.l + i * slot + slot / 2} y={height - 6} textAnchor="middle" className="tick">{c.label}</text>}
          </g>))}
      </svg>
      {hover != null && <div className="tip" style={{ left: Math.min(PAD.l + hover * slot + 8, width - 150), top: 4 }}><div className="tip-h">{groups[0].cols[hover].label}</div>
        {groups.map((g) => <div key={g.name}><i style={{ background: g.color }} /><span>{g.name}</span><b>{g.cols[hover]?.value ?? 0}{unit}</b></div>)}</div>}
      {groups.length > 1 && <ul className="legend">{groups.map((g) => <li key={g.name}><i style={{ background: g.color }} />{g.name}</li>)}</ul>}
    </div>
  );
}
