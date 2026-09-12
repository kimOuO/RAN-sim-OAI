'use client';

import { Fragment, useState } from 'react';
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
  // 2026-05-16 P4.3: row 展開狀態 — 點一下顯示 PDU body
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (key: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

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
              <Th style={{ width: 14 }}></Th>
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
            {rows.map((e) => {
              const key = `${e.service}-${e.seq}`;
              const isOpen = expanded.has(key);
              const hasPdu = (e.request_body && e.request_body.length > 0)
                || (e.response_body && e.response_body.length > 0);
              return (
                <Fragment key={key}>
                  <tr
                    style={{
                      borderBottom: isOpen ? 'none' : '1px solid #1f2937',
                      background: e.status >= 400 ? '#3f1d1d' : 'transparent',
                      cursor: hasPdu ? 'pointer' : 'default',
                    }}
                    onClick={() => { if (hasPdu) toggle(key); }}
                  >
                    <Td color={hasPdu ? '#9ca3af' : '#374151'}>
                      {hasPdu ? (isOpen ? '▼' : '▶') : ''}
                    </Td>
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
                  {isOpen && hasPdu && (
                    <tr style={{ borderBottom: '1px solid #1f2937' }}>
                      <td colSpan={8} style={{ padding: '6px 12px 10px 26px', background: '#0a0f1c' }}>
                        <PduDetail req={e.request_body || ''} resp={e.response_body || ''} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function PduDetail({ req, resp }: { req: string; resp: string }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
      <Block label="Request body" body={req} />
      <Block label="Response body" body={resp} />
    </div>
  );
}

function Block({ label, body }: { label: string; body: string }) {
  if (!body) {
    return (
      <div>
        <div style={{ fontSize: 9, color: '#6b7280', marginBottom: 3 }}>{label}</div>
        <div style={{ fontSize: 10, color: '#4b5563', fontStyle: 'italic' }}>(empty)</div>
      </div>
    );
  }
  // 嘗試 JSON pretty-print;不是 JSON 就原樣顯示
  let pretty = body;
  try {
    pretty = JSON.stringify(JSON.parse(body), null, 2);
  } catch {
    // body 不是 JSON,保留原始
  }
  return (
    <div>
      <div style={{ fontSize: 9, color: '#6b7280', marginBottom: 3, display: 'flex', justifyContent: 'space-between' }}>
        <span>{label}</span>
        <span style={{ color: '#374151' }}>{body.length}B {body.length >= 4096 ? '(truncated)' : ''}</span>
      </div>
      <pre style={{
        margin: 0,
        padding: 8,
        background: '#000',
        border: '1px solid #1f2937',
        borderRadius: 4,
        fontSize: 10,
        color: '#cbd5e1',
        maxHeight: 240,
        overflow: 'auto',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-all',
      }}>
        {pretty}
      </pre>
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
