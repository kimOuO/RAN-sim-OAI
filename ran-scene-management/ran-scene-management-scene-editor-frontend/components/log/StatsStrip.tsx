'use client';

import { SummaryStats } from '@/lib/logStats';

interface Props {
  stats: SummaryStats;
}

export function StatsStrip({ stats }: Props) {
  const errPct = stats.totalCount === 0 ? 0 : (stats.errorCount / stats.totalCount) * 100;
  const errOk = stats.errorCount === 0;
  const delta = stats.throughputPerSec - stats.prevThroughputPerSec;
  const arrow = delta > 0.1 ? '↗' : delta < -0.1 ? '↘' : '→';
  const arrowColor = delta > 0.1 ? '#10b981' : delta < -0.1 ? '#ef4444' : '#6b7280';

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16,
    }}>
      <Card title="📨 Throughput" valueColor="#cbd5e1">
        <div style={{ fontSize: 22, fontWeight: 700 }}>
          {stats.throughputPerSec.toFixed(1)}<span style={{ fontSize: 12, color: '#6b7280', fontWeight: 400 }}> msg/s</span>
        </div>
        <div style={{ fontSize: 11, color: arrowColor, marginTop: 2 }}>
          {arrow} {delta >= 0 ? '+' : ''}{delta.toFixed(1)} vs prev 5s
        </div>
      </Card>

      <Card title="🚨 Errors (30s)" valueColor={errOk ? '#10b981' : '#ef4444'}>
        <div style={{ fontSize: 22, fontWeight: 700 }}>
          {stats.errorCount}<span style={{ fontSize: 12, color: '#6b7280', fontWeight: 400 }}> / {stats.totalCount}</span>
        </div>
        <div style={{ fontSize: 11, color: errOk ? '#10b981' : '#dc2626', marginTop: 2 }}>
          {errOk ? '✓ all clean' : `${errPct.toFixed(1)}%`}
        </div>
      </Card>

      <Card title="⏱ Latency p95">
        <div style={{ fontSize: 22, fontWeight: 700 }}>
          {stats.p95DurationMs}<span style={{ fontSize: 12, color: '#6b7280', fontWeight: 400 }}> ms</span>
        </div>
        <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>
          max {stats.maxDurationMs} ms
        </div>
      </Card>

      <Card title="🔄 Active Categories">
        <div style={{ fontSize: 22, fontWeight: 700 }}>
          {stats.activeCategoryCount}<span style={{ fontSize: 12, color: '#6b7280', fontWeight: 400 }}> / {stats.totalCategoryCount}</span>
        </div>
        <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>
          CU:{stats.activePerService.CU} · DU:{stats.activePerService.DU} · RU:{stats.activePerService.RU}
        </div>
      </Card>
    </div>
  );
}

function Card({ title, children, valueColor }: { title: string; children: React.ReactNode; valueColor?: string }) {
  return (
    <div style={{
      background: '#111827', padding: '12px 14px', borderRadius: 8,
      border: '1px solid #374151', color: valueColor ?? '#cbd5e1',
    }}>
      <div style={{ fontSize: 11, color: '#9ca3af', fontWeight: 600, marginBottom: 4 }}>{title}</div>
      {children}
    </div>
  );
}
