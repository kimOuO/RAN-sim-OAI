'use client';

import { useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { RingEntry, bucketizeTimeline, colorForCategory } from '@/lib/logStats';

interface Props {
  logs: RingEntry[];
  now: number;
  windowMs?: number;
  bucketMs?: number;
  topN?: number;
}

export function ActivityTimeline({
  logs, now, windowMs = 60_000, bucketMs = 2_000, topN = 6,
}: Props) {
  const { data, topCats } = useMemo(() => {
    // 找 windowMs 內訊息數最多的前 N 個 category
    const cutoff = now - windowMs;
    const counts: Record<string, number> = {};
    for (const e of logs) {
      if (e.ts_ms < cutoff) continue;
      counts[e.category] = (counts[e.category] || 0) + 1;
    }
    const top = Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, topN)
      .map(([c]) => c);
    return {
      data: bucketizeTimeline(logs, now, top, windowMs, bucketMs),
      topCats: top,
    };
  }, [logs, now, windowMs, bucketMs, topN]);

  const hasData = topCats.length > 0;

  return (
    <div style={{
      background: '#111827', padding: 16, borderRadius: 8, border: '1px solid #374151',
    }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#cbd5e1' }}>
        📈 Activity Timeline ({windowMs / 1000}s, top {topN} categories, {bucketMs / 1000}s bucket)
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#9ca3af' }} interval={Math.floor(data.length / 8)} />
          <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} allowDecimals={false} />
          <Tooltip
            contentStyle={{ fontSize: 11, background: '#0b1220', border: '1px solid #374151', color: '#cbd5e1' }}
            labelFormatter={(l) => `${l} ago`}
          />
          <Legend wrapperStyle={{ fontSize: 10, color: '#cbd5e1' }} />
          {topCats.map((cat) => (
            <Area
              key={cat}
              type="monotone"
              dataKey={cat}
              stackId="1"
              stroke={colorForCategory(cat)}
              fill={colorForCategory(cat)}
              fillOpacity={0.85}
            />
          ))}
          <Area
            type="monotone"
            dataKey="other"
            stackId="1"
            stroke="#9ca3af"
            fill="#d1d5db"
            fillOpacity={0.5}
          />
        </AreaChart>
      </ResponsiveContainer>
      {!hasData && (
        <div style={{ fontSize: 11, color: '#9ca3af', textAlign: 'center', marginTop: -120, height: 0, position: 'relative' }}>
          No messages in window — start sim from /editor
        </div>
      )}
    </div>
  );
}
