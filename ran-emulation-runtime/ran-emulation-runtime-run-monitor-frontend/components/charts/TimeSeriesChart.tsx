'use client';
import { useMemo, useState } from 'react';
import { useElementWidth } from '@/hooks/base/useElementWidth';
import { fmtSimTime } from '@/hooks/feature/kpmDerive';
import type { Series } from '@/types/telemetry';

interface Props { series: Series[]; unit?: string; height?: number; yMin?: number; yMax?: number; xLabels?: number[]; digits?: number; legend?: boolean;
  /** 回放:目前時間所在的視窗索引(畫一條直線) */ cursor?: number | null;
  /** 回放:點圖跳到該視窗 */ onPick?: (i: number) => void; }
const PAD0 = { l: 44, r: 14, t: 10, b: 24 };
const CHAR_W = 6.4;   // .tick 為 10px 等寬字,一字約 6 px(取寬一點),用來算左邊留白
/** 多序列折線:淡格線、4 個 y 刻度、hover 十字線 + tooltip(列出該 x 所有序列值)、圖例。x = 視窗序;xLabels 提供 sim-time 秒。 */
export function TimeSeriesChart({ series, unit = '', height = 200, yMin, yMax, xLabels, digits = 1, legend = true, cursor = null, onPick }: Props) {
  const { ref, width } = useElementWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const n = Math.max(...series.map((s) => s.points.length), 0);
  const { lo, hi } = useMemo(() => {
    const ys = series.flatMap((s) => s.points.map((p) => p.y)).filter((v): v is number => v != null && Number.isFinite(v));
    let lo = yMin ?? (ys.length ? Math.min(...ys) : 0), hi = yMax ?? (ys.length ? Math.max(...ys) : 1);
    if (hi - lo < 1e-6) { hi = lo + 1; } if (yMin == null && lo > 0 && lo < (hi - lo) * 0.5) lo = 0;
    return { lo, hi };
  }, [series, yMin, yMax]);
  if (!n) return <div ref={ref} className="chart empty" style={{ height }}><span className="muted">尚無資料</span></div>;
  const yDigits = Math.abs(hi - lo) < 10 ? 1 : 0;
  const yTicks = [0, 1, 2, 3, 4].map((i) => lo + ((hi - lo) * i) / 4);
  const yLabel = (t: number) => `${t.toFixed(yDigits)}${unit}`;
  // 左邊留白依最長的刻度文字決定(含單位),避免「18 Mb/s」的首位數被切掉
  const PAD = { ...PAD0, l: Math.max(PAD0.l, Math.ceil(Math.max(...yTicks.map((t) => yLabel(t).length)) * CHAR_W) + 10) };
  const iw = width - PAD.l - PAD.r, ih = height - PAD.t - PAD.b;
  const px = (x: number) => PAD.l + (n > 1 ? (x / (n - 1)) * iw : iw / 2);
  const py = (y: number) => PAD.t + ih - ((y - lo) / (hi - lo)) * ih;
  const nx = Math.min(n, Math.max(2, Math.min(6, Math.floor(iw / 80))));   // 刻度不超過資料筆數，避免重複索引與標籤
  const xTickIdx = Array.from({ length: nx }, (_, i) => nx === 1 ? 0 : Math.round((i / (nx - 1)) * (n - 1)));
  const xl = (i: number) => (xLabels && xLabels[i] != null ? fmtSimTime(xLabels[i]) : String(i));
  const path = (s: Series) => { let d = '', pen = false; for (const p of s.points) { if (p.y == null) { pen = false; continue; } d += `${pen ? 'L' : 'M'}${px(p.x).toFixed(1)},${py(p.y).toFixed(1)}`; pen = true; } return d; };
  const onMove = (e: React.MouseEvent<SVGSVGElement>) => { const r = e.currentTarget.getBoundingClientRect(); const x = e.clientX - r.left - PAD.l; setHover(Math.max(0, Math.min(n - 1, Math.round((x / iw) * (n - 1))))); };
  const hv = hover != null ? series.map((s) => ({ s, y: s.points[hover]?.y ?? null })) : [];
  const tipLeft = hover != null ? Math.min(px(hover) + 10, width - 170) : 0;
  return (
    <div ref={ref} className="chart">
      <svg width={width} height={height} onMouseMove={onMove} onMouseLeave={() => setHover(null)} onClick={() => { if (onPick && hover != null) onPick(hover); }} style={onPick ? { cursor: 'pointer' } : undefined} role="img" aria-label={`${series.length} series line chart`}>
        {yTicks.map((t) => <g key={t}><line x1={PAD.l} x2={width - PAD.r} y1={py(t)} y2={py(t)} className="grid" /><text x={PAD.l - 6} y={py(t) + 3.5} textAnchor="end" className="tick">{yLabel(t)}</text></g>)}
        {xTickIdx.map((i, k) => <text key={i} x={px(i)} y={height - 6} textAnchor={nx > 1 && k === 0 ? 'start' : nx > 1 && k === nx - 1 ? 'end' : 'middle'} className="tick">{xl(i)}</text>)}
        <line x1={PAD.l} x2={width - PAD.r} y1={PAD.t + ih} y2={PAD.t + ih} className="axis" />
        {series.map((s) => <path key={s.key} d={path(s)} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" />)}
        {cursor != null && cursor >= 0 && cursor < n && <line x1={px(cursor)} x2={px(cursor)} y1={PAD.t} y2={PAD.t + ih} className="now" />}
        {hover != null && <g><line x1={px(hover)} x2={px(hover)} y1={PAD.t} y2={PAD.t + ih} className="cross" />
          {hv.map(({ s, y }) => y != null && <circle key={s.key} cx={px(hover)} cy={py(y)} r="4" fill={s.color} stroke="var(--bg-2)" strokeWidth="2" />)}</g>}
      </svg>
      {hover != null && <div className="tip" style={{ left: tipLeft, top: 8 }}><div className="tip-h">{xl(hover)}</div>
        {hv.map(({ s, y }) => <div key={s.key}><i style={{ background: s.color }} /><span>{s.label}</span><b>{y == null ? '—' : `${y.toFixed(digits)}${unit}`}</b></div>)}</div>}
      {legend && series.length > 1 && <ul className="legend">{series.map((s) => <li key={s.key}><i style={{ background: s.color }} />{s.label}</li>)}</ul>}
    </div>
  );
}
