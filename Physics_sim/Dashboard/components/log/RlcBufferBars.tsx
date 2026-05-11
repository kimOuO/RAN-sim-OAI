'use client';

import { useEffect, useMemo, useState } from 'react';
import { DU_BASE_URL } from '@/config';

const C_CARD = '#111827';
const C_BORDER = '#374151';
const C_TEXT = '#cbd5e1';
const C_MUTED = '#6b7280';

interface BufferRow {
  ue_id: string;
  bearer_type: string;       // SRB / DRB
  bearer_id: number;
  mode?: string;             // AM / UM
  buffer_occupancy: number;  // bytes
}

const POLL_MS = 2000;
const BAR_COLORS = ['#06b6d4', '#10b981', '#f59e0b', '#a855f7', '#ef4444'];

export function RlcBufferBars() {
  const [rows, setRows] = useState<BufferRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const r = await fetch(
          `${DU_BASE_URL}/api/v0.1/DU/RLC/RlcDataController/read_buffer_status`,
          { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' },
        );
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        if (stop) return;
        const arr = j?.data?.entities || j?.data?.entries || j?.data || [];
        setRows((Array.isArray(arr) ? arr : []) as BufferRow[]);
        setError('');
        setLoading(false);
      } catch (e: any) {
        if (stop) return;
        setError(e?.message || String(e));
        setLoading(false);
      }
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { stop = true; clearInterval(id); };
  }, []);

  // group by ue_id
  const groups = useMemo(() => {
    const m = new Map<string, BufferRow[]>();
    for (const r of rows) {
      const k = r.ue_id || 'unknown';
      const arr = m.get(k) || [];
      arr.push(r);
      m.set(k, arr);
    }
    return Array.from(m.entries()).map(([ue_id, items]) => ({
      ue_id,
      items,
      total: items.reduce((a, b) => a + (b.buffer_occupancy || 0), 0),
    }));
  }, [rows]);

  const maxBytes = Math.max(1, ...groups.map(g => g.total));

  return (
    <section style={{ marginBottom: 24 }}>
      <h2 style={{
        margin: 0, color: C_TEXT, fontSize: 14, fontWeight: 600,
        marginBottom: 12,
      }}>
        📦 RLC Buffer Occupancy （per UE × bearer，bytes 待傳）
      </h2>
      <div style={{
        background: C_CARD, border: `1px solid ${C_BORDER}`, borderRadius: 8,
        padding: 12,
      }}>
        {error && <div style={{ color: '#ef4444', fontSize: 11 }}>err: {error}</div>}
        {loading && groups.length === 0 ? (
          <div style={{ color: C_MUTED, fontSize: 12 }}>loading...</div>
        ) : groups.length === 0 ? (
          <div style={{ color: C_MUTED, fontSize: 12 }}>(no RLC entities — UE 未 attach 或無 traffic)</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {groups.map(g => (
              <div key={g.ue_id} style={{ display: 'grid', gridTemplateColumns: '120px 1fr 100px', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: C_TEXT, fontFamily: 'monospace' }}>
                  {g.ue_id}
                </span>
                <div style={{
                  position: 'relative', background: '#0b1220',
                  borderRadius: 4, height: 22, overflow: 'hidden',
                  display: 'flex',
                }}>
                  {g.items.map((it, idx) => {
                    const w = (it.buffer_occupancy / maxBytes) * 100;
                    if (w === 0) return null;
                    return (
                      <div key={`${it.bearer_type}-${it.bearer_id}`} style={{
                        width: `${w}%`,
                        background: BAR_COLORS[idx % BAR_COLORS.length],
                        height: '100%',
                      }} title={`${it.bearer_type}-${it.bearer_id} ${it.mode ?? ''} · ${it.buffer_occupancy} bytes`} />
                    );
                  })}
                </div>
                <span style={{
                  fontSize: 11, color: C_MUTED, fontFamily: 'monospace', textAlign: 'right',
                }}>
                  {g.total.toLocaleString()} B
                </span>
              </div>
            ))}
          </div>
        )}
        <div style={{
          fontSize: 9, color: C_MUTED, marginTop: 12,
          display: 'flex', gap: 12, flexWrap: 'wrap',
        }}>
          <span>顏色 = 不同 bearer (DRB1, DRB2, ...):</span>
          {BAR_COLORS.slice(0, 3).map((c, i) => (
            <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, background: c }} /> bearer {i + 1}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
