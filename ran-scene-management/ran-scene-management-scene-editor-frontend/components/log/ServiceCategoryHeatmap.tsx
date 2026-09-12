'use client';

import { useMemo } from 'react';
import {
  RingEntry, CATEGORY_GROUPS, GROUP_LABEL,
  serviceGroupHeatmap,
} from '@/lib/logStats';

interface Props {
  logs: RingEntry[];
  now: number;
  windowMs?: number;
}

const SERVICES: Array<'CU' | 'DU' | 'RU'> = ['CU', 'DU', 'RU'];
const SVC_BG: Record<string, string> = {
  CU: '#1e3a8a', DU: '#064e3b', RU: '#78350f',
};
const SVC_LABEL: Record<string, string> = {
  CU: '#93c5fd', DU: '#6ee7b7', RU: '#fcd34d',
};

function cellStyle(count: number, max: number): React.CSSProperties {
  if (count === 0) {
    return { background: '#0b1220', color: '#4b5563' };
  }
  // dark theme：深底 → 螢光藍
  const ratio = max === 0 ? 0 : Math.min(1, count / max);
  const lightness = 25 + ratio * 35; // 25% (dark) → 60% (vibrant)
  return {
    background: `hsl(217, 80%, ${lightness}%)`,
    color: lightness < 45 ? '#cbd5e1' : '#0b1220',
    fontWeight: 600,
  };
}

export function ServiceCategoryHeatmap({ logs, now, windowMs = 30_000 }: Props) {
  const { cells, maxCount } = useMemo(
    () => serviceGroupHeatmap(logs, now, windowMs),
    [logs, now, windowMs]
  );
  const cellByKey: Record<string, number> = {};
  for (const c of cells) cellByKey[`${c.service}|${c.group}`] = c.count;

  return (
    <div style={{
      background: '#111827', padding: 16, borderRadius: 8, border: '1px solid #374151',
    }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#cbd5e1' }}>
        🟦 Service × Category Group (last {windowMs / 1000}s)
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: `auto repeat(${CATEGORY_GROUPS.length}, 1fr)`,
        gap: 4,
        fontSize: 11,
      }}>
        {/* header row */}
        <div></div>
        {CATEGORY_GROUPS.map((g) => (
          <div key={g} style={{
            textAlign: 'center', padding: '4px 2px', fontWeight: 600, color: '#9ca3af',
          }}>
            {GROUP_LABEL[g]}
          </div>
        ))}

        {/* data rows */}
        {SERVICES.map((svc) => (
          <Row key={svc}>
            <div style={{
              padding: '8px 12px', borderRadius: 4,
              background: SVC_BG[svc], color: SVC_LABEL[svc], fontWeight: 700,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {svc}
            </div>
            {CATEGORY_GROUPS.map((g) => {
              const count = cellByKey[`${svc}|${g}`] || 0;
              return (
                <div
                  key={`${svc}|${g}`}
                  style={{
                    padding: '8px 4px',
                    borderRadius: 4,
                    textAlign: 'center',
                    fontFamily: 'monospace',
                    fontSize: 12,
                    ...cellStyle(count, maxCount),
                  }}
                  title={`${svc} × ${GROUP_LABEL[g]}: ${count} msg`}
                >
                  {count === 0 ? '·' : count}
                </div>
              );
            })}
          </Row>
        ))}
      </div>
      <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
        <span>低</span>
        <div style={{ display: 'flex', gap: 1, height: 8, flex: 1, maxWidth: 120 }}>
          {[25, 32, 40, 48, 54, 60].map((l) => (
            <div key={l} style={{ flex: 1, background: `hsl(217, 80%, ${l}%)` }} />
          ))}
        </div>
        <span>高</span>
        <span style={{ marginLeft: 12, color: '#6b7280' }}>
          黑=零、亮=訊息越多。max={maxCount}
        </span>
      </div>
    </div>
  );
}

// React fragment helper to keep grid happy without extra DOM
function Row({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
