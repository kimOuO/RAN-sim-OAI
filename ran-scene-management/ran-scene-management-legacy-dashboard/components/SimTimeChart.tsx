'use client';

import dynamic from 'next/dynamic';

const LineChart = dynamic(() => import('recharts').then(m => m.LineChart), { ssr: false });
const Line = dynamic(() => import('recharts').then(m => m.Line), { ssr: false });
const XAxis = dynamic(() => import('recharts').then(m => m.XAxis), { ssr: false });
const YAxis = dynamic(() => import('recharts').then(m => m.YAxis), { ssr: false });
const CartesianGrid = dynamic(() => import('recharts').then(m => m.CartesianGrid), { ssr: false });
const Tooltip = dynamic(() => import('recharts').then(m => m.Tooltip), { ssr: false });
const Legend = dynamic(() => import('recharts').then(m => m.Legend), { ssr: false });
const ResponsiveContainer = dynamic(() => import('recharts').then(m => m.ResponsiveContainer), { ssr: false });
const ReferenceLine = dynamic(() => import('recharts').then(m => m.ReferenceLine), { ssr: false });

export interface SimTimeChartProps {
  data: Array<Record<string, number>>;     // 每筆需含 'tick'(sim-sec 整數)
  scenarioStart: string;                    // e.g. "10:00:00"
  leftSeries: Array<{ key: string; label: string; color: string }>;   // 走左 Y 軸
  rightSeries?: Array<{ key: string; label: string; color: string }>; // 走右 Y 軸
  leftLabel?: string;
  rightLabel?: string;
  height?: number;
  // 在指定 sim-sec 處畫垂直 reference line(e.g. handover 觸發時刻)
  markers?: Array<{ tick: number; color: string; label?: string }>;
  // 目前游標 sim-sec(可選,在圖上畫一條垂直線標記「現在」)
  cursor?: number;
  // Compact 模式給 card 預覽用:藏 legend / label / grid 化簡
  compact?: boolean;
}

/** sim-sec offset → HH:MM:SS string,基於 scenarioStart */
function simSecToHMS(start: string, sec: number): string {
  const [h, m, s] = start.split(':').map(Number);
  const tot = (h * 3600 + m * 60 + s) + Math.floor(sec);
  const hh = Math.floor(tot / 3600) % 24;
  const mm = Math.floor((tot % 3600) / 60);
  const ss = tot % 60;
  return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
}

export function SimTimeChart({
  data, scenarioStart,
  leftSeries, rightSeries = [],
  leftLabel = '', rightLabel = '',
  height = 200, markers = [], cursor, compact = false,
}: SimTimeChartProps) {
  if (!data || data.length === 0) {
    return (
      <div style={{
        height, display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#64748b', fontSize: 11, background: '#0f172a', borderRadius: 4,
      }}>
        {compact ? '—' : 'No data yet'}
      </div>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={
        compact ? { top: 2, right: 6, left: 6, bottom: 2 }
                : { top: 5, right: 50, left: 20, bottom: 5 }
      }>
        {!compact && <CartesianGrid strokeDasharray="3 3" stroke="#334155" />}
        <XAxis
          dataKey="tick" type="number"
          domain={['dataMin', 'dataMax']}
          tickFormatter={(v: number) => simSecToHMS(scenarioStart, v)}
          stroke="#94a3b8"
          tick={{ fontSize: compact ? 8 : 10 }}
          // compact 模式仍 show X 軸,但只顯示首尾兩個 tick
          interval={compact ? 'preserveStartEnd' : 0}
          minTickGap={compact ? 80 : 20}
        />
        <YAxis yAxisId="left" stroke="#94a3b8" tick={{ fontSize: compact ? 8 : 10 }}
          width={compact ? 28 : 50}
          label={(!compact && leftLabel) ? { value: leftLabel, angle: -90, position: 'insideLeft', fill: '#94a3b8', fontSize: 10 } : undefined} />
        {rightSeries.length > 0 && (
          <YAxis yAxisId="right" orientation="right" stroke="#94a3b8" tick={{ fontSize: compact ? 8 : 10 }}
            width={compact ? 28 : 50}
            label={(!compact && rightLabel) ? { value: rightLabel, angle: 90, position: 'insideRight', fill: '#94a3b8', fontSize: 10 } : undefined} />
        )}
        {!compact && (
          <Tooltip
            labelFormatter={(v: number) => `sim ${simSecToHMS(scenarioStart, v)}`}
            contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 11 }}
          />
        )}
        {!compact && <Legend wrapperStyle={{ fontSize: 11 }} />}
        {leftSeries.map(s => (
          <Line key={s.key} yAxisId="left" type="monotone"
            dataKey={s.key} name={s.label} stroke={s.color}
            dot={false} isAnimationActive={false}
            strokeWidth={compact ? 1.5 : 2} />
        ))}
        {rightSeries.map(s => (
          <Line key={s.key} yAxisId="right" type="monotone"
            dataKey={s.key} name={s.label} stroke={s.color}
            dot={false} isAnimationActive={false}
            strokeWidth={compact ? 1.5 : 2}
            strokeDasharray="4 2" />
        ))}
        {markers.map((m, i) => (
          <ReferenceLine key={i} yAxisId="left" x={m.tick} stroke={m.color}
            strokeDasharray="2 2"
            label={(!compact && m.label) ? { value: m.label, fill: m.color, fontSize: 10 } : undefined} />
        ))}
        {cursor !== undefined && (
          <ReferenceLine yAxisId="left" x={cursor} stroke="#ef4444" strokeWidth={1.5} />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
