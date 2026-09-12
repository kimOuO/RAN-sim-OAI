'use client';

import { useEffect, useState } from 'react';
import { E2_ADAPTER_BASE_URL } from '@/config';

interface MetricEntry {
  name: string;
  value: number | null;
  unit: string;
  ts_ms: number;
  serving_cell: string;
}

interface UeSnapshot {
  ue_id: string;
  metrics: MetricEntry[];
}

interface SnapshotData {
  ues: UeSnapshot[];
  last_update_ms: number;
  total_indications: number;
}

const POLL_MS = 2000;

// Standard 9 KPM metrics 順序（對齊 sim CU 跟 ASN.1 schema）
const METRIC_ORDER = [
  'DRB.UEThpDl', 'DRB.UEThpUl',
  'DRB.PdcpSduVolumeDL', 'DRB.PdcpSduVolumeUL',
  'DRB.RlcSduDelayDl',
  'RRU.PrbTotDl', 'RRU.PrbTotUl',
  'RSRP', 'SINR',
];

const UNIT_COLOR: Record<string, string> = {
  kbps: '#10b981', bytes: '#3b82f6', ms: '#f59e0b', '%': '#a855f7',
  dBm: '#06b6d4', dB: '#ef4444',
};

function fmtTs(ms: number): string {
  if (!ms) return '—';
  const ageSec = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  if (ageSec < 5) return `${ageSec}s ago`;
  if (ageSec < 60) return `${ageSec}s ago`;
  return `${Math.floor(ageSec / 60)}m ago`;
}

function fmtValue(v: number | null, unit: string): string {
  if (v === null || v === undefined) return '—';
  if (unit === '%') return `${v.toFixed(1)}%`;
  if (unit === 'dBm' || unit === 'dB') return `${v.toFixed(1)}`;
  if (Number.isInteger(v)) return v.toLocaleString();
  return v.toFixed(2);
}

export function E2KpmPanel() {
  const [data, setData] = useState<SnapshotData | null>(null);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    let cancelled = false;
    const pollOnce = async () => {
      try {
        const resp = await fetch(
          `${E2_ADAPTER_BASE_URL}/api/v0.1/E2Adapter/KpmSnapshot/SnapshotReader/read`,
          { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' },
        );
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();
        if (cancelled) return;
        setData(json.data);
        setError('');
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.message || String(e));
      }
    };
    pollOnce();
    const id = setInterval(pollOnce, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  return (
    <div style={{
      background: '#111827', border: '1px solid #374151', borderRadius: 10,
      padding: 16, marginTop: 16,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    marginBottom: 12 }}>
        <h3 style={{ margin: 0, color: '#f3f4f6', fontSize: 16 }}>
          📊 KPM 指標數值（adapter snapshot — 跟 RIC 看到的同一份）
        </h3>
        <span style={{ fontSize: 11, color: '#6b7280' }}>
          {data ? (
            <>
              {data.ues.length} UE · {data.total_indications} indications · last {fmtTs(data.last_update_ms)} · poll {POLL_MS}ms
            </>
          ) : (error ? <span style={{ color: '#ef4444' }}>err: {error}</span> : 'loading...')}
        </span>
      </div>

      {!data || data.ues.length === 0 ? (
        <div style={{ color: '#6b7280', fontSize: 12, fontFamily: 'monospace', padding: 8 }}>
          (尚無 KPM 資料 — adapter 跟 RIC 對通 + xApp 訂閱後 1 秒內會出現)
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{
            width: '100%', borderCollapse: 'collapse',
            fontFamily: 'monospace', fontSize: 11,
          }}>
            <thead>
              <tr style={{ background: '#0f172a', borderBottom: '2px solid #374151' }}>
                <th style={th}>UE ID</th>
                <th style={th}>Cell</th>
                {METRIC_ORDER.map(m => (
                  <th key={m} style={th} title={m}>{m}</th>
                ))}
                <th style={th}>更新</th>
              </tr>
            </thead>
            <tbody>
              {data.ues.map(ue => {
                const byName: Record<string, MetricEntry> = {};
                ue.metrics.forEach(m => { byName[m.name] = m; });
                const latestTs = Math.max(0, ...ue.metrics.map(m => m.ts_ms));
                const cell = ue.metrics[0]?.serving_cell || '—';
                return (
                  <tr key={ue.ue_id} style={{ borderBottom: '1px solid #1f2937' }}>
                    <td style={{ ...td, color: '#a855f7', fontWeight: 600 }}>{ue.ue_id}</td>
                    <td style={{ ...td, color: '#94a3b8' }}>{cell || '—'}</td>
                    {METRIC_ORDER.map(name => {
                      const m = byName[name];
                      const color = m ? (UNIT_COLOR[m.unit] || '#cbd5e1') : '#4b5563';
                      return (
                        <td key={name} style={{ ...td, color, textAlign: 'right' }}>
                          {m ? fmtValue(m.value, m.unit) : '—'}
                          {m && m.unit && m.value !== null && (
                            <span style={{ color: '#6b7280', marginLeft: 3 }}>{m.unit}</span>
                          )}
                        </td>
                      );
                    })}
                    <td style={{ ...td, color: '#6b7280' }}>{fmtTs(latestTs)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const th: React.CSSProperties = {
  padding: '6px 8px', textAlign: 'left', color: '#cbd5e1', fontWeight: 600,
  fontSize: 10, whiteSpace: 'nowrap',
};
const td: React.CSSProperties = {
  padding: '6px 8px', whiteSpace: 'nowrap',
};
