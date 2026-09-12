'use client';

import { useMemo } from 'react';
import { CircularProgressbar, buildStyles } from 'react-circular-progressbar';
import 'react-circular-progressbar/dist/styles.css';
import {
  LineChart, Line, ResponsiveContainer, YAxis, Tooltip,
} from 'recharts';
import { useCellStatus, type CellAggregate } from '@/hooks/feature/log/useCellStatus';
import { useHandoverEvents } from '@/hooks/feature/log/useHandoverEvents';
import type { RingEntry } from '@/lib/logStats';

const C_CARD = '#111827';
const C_BORDER = '#374151';
const C_TEXT = '#cbd5e1';
const C_MUTED = '#6b7280';
const C_OK = '#10b981';
const C_WARN = '#f59e0b';
const C_FAIL = '#ef4444';

interface Props {
  logs: RingEntry[];
}

export function CellStatusGrid({ logs }: Props) {
  const { aggregates, loading } = useCellStatus();
  const ho = useHandoverEvents(logs, 60);

  // map ue_id → cell (for HO origin attribution)
  const hoByCell = useMemo(() => {
    const map = new Map<string, number>();
    for (const e of ho) {
      if (!e.ue_id) continue;
      // We don't know source/target from path alone, attribute to ue_id's currently
      // serving cell as proxy. (See useHandoverEvents caveat.)
      const ue = aggregates.find(a => a.cell.cell_id === e.source_cell);
      if (ue) {
        map.set(ue.cell.cell_id, (map.get(ue.cell.cell_id) || 0) + 1);
      }
    }
    return map;
  }, [ho, aggregates]);

  return (
    <section style={{ marginBottom: 24 }}>
      <h2 style={{
        margin: 0, color: C_TEXT, fontSize: 14, fontWeight: 600,
        marginBottom: 12,
      }}>
        🛰 Cell Status Grid
      </h2>
      {loading && aggregates.length === 0 ? (
        <div style={{ color: C_MUTED, fontSize: 12 }}>loading cell snapshots...</div>
      ) : aggregates.length === 0 ? (
        <div style={{
          background: C_CARD, border: `1px solid ${C_BORDER}`, borderRadius: 8,
          padding: 16, color: C_MUTED, fontSize: 12,
        }}>
          (no cells reported by DU MacCellController)
        </div>
      ) : (
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: 12,
        }}>
          {aggregates.map(agg => (
            <CellCard key={agg.cell.cell_id} agg={agg}
                      hoCount={hoByCell.get(agg.cell.cell_id) || 0} />
          ))}
        </div>
      )}
    </section>
  );
}


function CellCard({ agg, hoCount }: { agg: CellAggregate; hoCount: number }) {
  const prbColor = agg.prbUsedPct >= 85 ? C_FAIL
    : agg.prbUsedPct >= 60 ? C_WARN
    : C_OK;
  const sinrColor = (agg.avgSinrDb ?? 0) >= 12 ? C_OK
    : (agg.avgSinrDb ?? 0) >= 5 ? C_WARN
    : C_FAIL;
  const retxColor = agg.retxRatePct < 5 ? C_OK
    : agg.retxRatePct < 15 ? C_WARN
    : C_FAIL;

  const sparkData = agg.sinrHistory.map((v, i) => ({ i, v }));

  return (
    <div style={{
      background: C_CARD, border: `1px solid ${C_BORDER}`, borderRadius: 8,
      padding: 12,
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
        marginBottom: 8, paddingBottom: 8, borderBottom: `1px solid ${C_BORDER}`,
      }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: C_TEXT, fontFamily: 'monospace' }}>
          {agg.cell.cell_id}
        </span>
        <span style={{ fontSize: 11, color: C_MUTED }}>
          {agg.ueCount} UE attached
        </span>
      </div>

      {/* 2026-05-16 P4.2: PCI + nr_cellid 對齊資訊。
          nr_cellid 有填 (explicit OAI 真值) → 綠色 +「OAI」標籤
          沒填 → 灰色 +「hash」標籤 (走 SHA-1 fallback) */}
      <div style={{
        display: 'flex', gap: 12, marginBottom: 10, fontSize: 10, fontFamily: 'monospace',
      }}>
        <span style={{ color: C_MUTED }}>
          PCI <span style={{ color: C_TEXT }}>{agg.cell.pci ?? '—'}</span>
        </span>
        <span style={{ color: C_MUTED }}>
          nr_cellid{' '}
          {agg.cell.nr_cellid != null ? (
            <span style={{ color: '#10b981' }}>{agg.cell.nr_cellid} (OAI)</span>
          ) : (
            <span style={{ color: '#6b7280' }}>hash</span>
          )}
        </span>
      </div>

      {/* Body: gauge + sparkline */}
      <div style={{
        display: 'grid', gridTemplateColumns: '80px 1fr', gap: 12,
        alignItems: 'center', marginBottom: 12,
      }}>
        <div style={{ width: 70, height: 70 }}>
          <CircularProgressbar
            value={agg.prbUsedPct}
            text={`${agg.prbUsedPct.toFixed(0)}%`}
            styles={buildStyles({
              pathColor: prbColor,
              textColor: prbColor,
              trailColor: '#1f2937',
              textSize: '24px',
            })}
          />
        </div>
        <div>
          <div style={{ fontSize: 10, color: C_MUTED, marginBottom: 2 }}>SINR (last 30 ticks)</div>
          <div style={{ height: 40 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={sparkData}>
                <YAxis hide domain={['auto', 'auto']} />
                <Tooltip
                  contentStyle={{ background: '#0b1220', border: `1px solid ${C_BORDER}`, fontSize: 11 }}
                  labelFormatter={() => ''}
                  formatter={(v: any) => [`${Number(v).toFixed(1)} dB`, 'SINR']}
                />
                <Line type="monotone" dataKey="v" stroke={sinrColor}
                      strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, color: sinrColor, fontFamily: 'monospace' }}>
            {agg.avgSinrDb !== null ? `${agg.avgSinrDb.toFixed(1)} dB` : '—'}
          </div>
        </div>
      </div>

      {/* Footer KPIs */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8,
        fontSize: 11, fontFamily: 'monospace',
      }}>
        <KpiMini label="HARQ retx" value={`${agg.retxRatePct.toFixed(1)}%`} color={retxColor} />
        <KpiMini label="HO 60s" value={`${hoCount}`} color={C_TEXT} />
      </div>
    </div>
  );
}


function KpiMini({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{
      background: '#0b1220', borderRadius: 4, padding: '6px 8px',
    }}>
      <div style={{ fontSize: 9, color: C_MUTED, textTransform: 'uppercase' }}>
        {label}
      </div>
      <div style={{ fontSize: 13, color, fontWeight: 600 }}>{value}</div>
    </div>
  );
}
