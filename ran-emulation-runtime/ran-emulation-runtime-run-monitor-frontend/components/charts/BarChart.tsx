'use client';
import { useState } from 'react';
import { useElementWidth } from '@/hooks/base/useElementWidth';

interface Bar { label: string; value: number; color: string; sub?: string; }
/** 橫向長條(cell 當下的量),4px 圓角資料端,hover tooltip */
export function BarChart({ bars, unit = '', max, height }: { bars: Bar[]; unit?: string; max?: number; height?: number }) {
  const { ref, width } = useElementWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const hi = max ?? Math.max(1, ...bars.map((b) => b.value));
  const rowH = 26, L = 90, R = 56; const h = height ?? bars.length * rowH + 8;
  if (!bars.length) return <div ref={ref} className="chart empty" style={{ height: 60 }}><span className="muted">尚無資料</span></div>;
  return (
    <div ref={ref} className="chart">
      <svg width={width} height={h} role="img" aria-label="bar chart">
        {bars.map((b, i) => { const w = Math.max(2, ((width - L - R) * b.value) / hi); const y = 4 + i * rowH; return (
          <g key={b.label} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <rect x={L} y={y} width={width - L - R} height={rowH - 8} className="bar-track" />
            <rect x={L} y={y} width={w} height={rowH - 8} rx="3" fill={b.color} opacity={hover == null || hover === i ? 1 : 0.55} />
            <text x={L - 8} y={y + rowH / 2 - 1} textAnchor="end" className="lbl">{b.label}</text>
            <text x={L + w + 6} y={y + rowH / 2 - 1} className="val">{b.value.toFixed(1)}{unit}{b.sub ? ` · ${b.sub}` : ''}</text>
          </g>); })}
      </svg>
    </div>
  );
}
