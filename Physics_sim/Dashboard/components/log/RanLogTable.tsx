'use client';

import { RingEntry } from '@/lib/logStats';

interface Props {
  entries: RingEntry[];
  autoScroll: boolean;
  maxRows?: number;
}

const SVC_COLORS: Record<string, string> = {
  CU: '#3b82f6', DU: '#10b981', RU: '#f59e0b',
};

export function RanLogTable({ entries, autoScroll, maxRows = 60 }: Props) {
  const rows = autoScroll
    ? entries.slice(-maxRows).slice().reverse()
    : entries.slice(0, maxRows);

  return (
    <div style={{
      background: '#0b1220', padding: 12, borderRadius: 8,
      border: '1px solid #374151', maxHeight: 380, overflowY: 'auto',
    }}>
      {rows.length === 0 ? (
        <div style={{ fontSize: 12, color: '#6b7280', padding: 24, textAlign: 'center' }}>
          沒有符合條件的訊息
        </div>
      ) : (
        <table style={{ fontSize: 10.5, width: '100%', borderCollapse: 'collapse', fontFamily: 'monospace' }}>
          <thead style={{ position: 'sticky', top: 0, background: '#0b1220' }}>
            <tr style={{ borderBottom: '1px solid #374151', textAlign: 'left' }}>
              <Th>t</Th>
              <Th>SVC</Th>
              <Th>Category</Th>
              <Th>UE</Th>
              <Th style={{ minWidth: 200 }}>Path</Th>
              <Th align="right">ms</Th>
              <Th align="right">code</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={`${e.service}-${e.seq}`} style={{
                borderBottom: '1px solid #1f2937',
                background: e.status >= 400 ? '#3f1d1d' : 'transparent',
              }}>
                <Td color="#6b7280">{formatT(e.ts_ms)}</Td>
                <Td>
                  <span style={{
                    background: SVC_COLORS[e.service] || '#6b7280',
                    color: '#fff', padding: '1px 5px', borderRadius: 3,
                    fontSize: 9, fontWeight: 700,
                  }}>
                    {e.service}
                  </span>
                </Td>
                <Td bold color="#cbd5e1">{e.category}</Td>
                <Td color="#9ca3af">{e.ue_id || '-'}</Td>
                <Td color="#9ca3af" title={e.path}>
                  <span style={{ display: 'inline-block', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', verticalAlign: 'middle' }}>
                    {shortenPath(e.path)}
                  </span>
                </Td>
                <Td align="right" color={e.duration_ms > 100 ? '#f59e0b' : '#6b7280'}>
                  {e.duration_ms}
                </Td>
                <Td align="right" color={e.status >= 400 ? '#ef4444' : '#10b981'} bold>
                  {e.status}
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function formatT(ts: number) {
  const d = new Date(ts);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${String(d.getMilliseconds()).padStart(3, '0')}`;
}
function pad(n: number) { return String(n).padStart(2, '0'); }

function shortenPath(p: string): string {
  return p.replace(/^\/api\/v0\.1\//, '');
}

function Th({ children, align, style }: { children: React.ReactNode; align?: 'right'; style?: React.CSSProperties }) {
  return <th style={{ padding: 4, textAlign: align ?? 'left', fontSize: 10, color: '#6b7280', fontWeight: 600, ...style }}>{children}</th>;
}

function Td(props: { children: React.ReactNode; align?: 'right'; color?: string; bold?: boolean; title?: string }) {
  const { children, align, color, bold, title } = props;
  return (
    <td title={title} style={{
      padding: '3px 4px',
      textAlign: align ?? 'left',
      color: color,
      fontWeight: bold ? 600 : 400,
    }}>
      {children}
    </td>
  );
}
