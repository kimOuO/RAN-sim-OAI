'use client';

import { useMemo } from 'react';
import { RingEntry, topCategoriesWithStats, colorForCategory } from '@/lib/logStats';

interface Props {
  logs: RingEntry[];
  now: number;
  windowMs?: number;
  topN?: number;
}

export function TopCategoriesPanel({
  logs, now, windowMs = 30_000, topN = 8,
}: Props) {
  const stats = useMemo(
    () => topCategoriesWithStats(logs, now, windowMs, topN),
    [logs, now, windowMs, topN]
  );
  const max = stats[0]?.count || 1;

  return (
    <div style={{
      background: '#111827', padding: 16, borderRadius: 8, border: '1px solid #374151',
    }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#cbd5e1' }}>
        ⏱ Top categories — count + latency + errors (last {windowMs / 1000}s)
      </div>

      {stats.length === 0 ? (
        <div style={{ fontSize: 12, color: '#6b7280', padding: '16px 0' }}>
          沒有訊息 — start sim 後就會出現
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Header />
          {stats.map((s) => {
            const hasError = s.errorCount > 0;
            return (
              <div
                key={s.category}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '140px 1fr 50px 50px 50px 50px',
                  gap: 8, alignItems: 'center', fontSize: 11,
                  fontFamily: 'monospace',
                  color: hasError ? '#fca5a5' : '#cbd5e1',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={s.category}>
                  {s.category}
                </div>
                <div style={{ height: 14, background: '#1f2937', borderRadius: 3, position: 'relative' }}>
                  <div style={{
                    height: '100%', width: `${(s.count / max) * 100}%`,
                    background: colorForCategory(s.category),
                    borderRadius: 3,
                    transition: 'width 200ms ease',
                  }} />
                </div>
                <div style={{ textAlign: 'right' }}>{s.count}</div>
                <div style={{ textAlign: 'right', color: '#9ca3af' }}>{s.p50}</div>
                <div style={{ textAlign: 'right', color: '#9ca3af' }}>{s.p95}</div>
                <div style={{ textAlign: 'right', color: hasError ? '#ef4444' : '#10b981', fontWeight: hasError ? 700 : 400 }}>
                  {hasError ? s.errorCount : '✓'}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Header() {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '140px 1fr 50px 50px 50px 50px',
      gap: 8, alignItems: 'center',
      fontSize: 10, color: '#9ca3af', fontWeight: 600,
      borderBottom: '1px solid #1f2937', paddingBottom: 4,
    }}>
      <div>category</div>
      <div>count</div>
      <div style={{ textAlign: 'right' }}>n</div>
      <div style={{ textAlign: 'right' }}>p50</div>
      <div style={{ textAlign: 'right' }}>p95</div>
      <div style={{ textAlign: 'right' }}>err</div>
    </div>
  );
}
