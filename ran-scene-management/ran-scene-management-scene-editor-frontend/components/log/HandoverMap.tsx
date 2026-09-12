'use client';

import { useMemo } from 'react';
import { ResponsiveSankey } from '@nivo/sankey';
import { useHandoverEventApi } from '@/hooks/feature/log/useHandoverEventApi';
import type { HoTrigger } from '@/hooks/feature/log/useHandoverEvents';

const C_CARD = '#111827';
const C_BORDER = '#374151';
const C_TEXT = '#cbd5e1';
const C_MUTED = '#6b7280';

const TRIG_COLORS: Record<HoTrigger, string> = {
  A3_TTT: '#10b981',
  E2_RIC_CONTROL: '#a855f7',
  MANUAL: '#f59e0b',
  UNKNOWN: '#6b7280',
};

const sourceNodeId = (cellId: string) => `${cellId} source`;
const targetNodeId = (cellId: string) => `${cellId} target`;

interface Props {
  windowSec?: number;
}

export function HandoverMap({ windowSec = 300 }: Props) {
  const events = useHandoverEventApi(windowSec);

  const counts = useMemo(() => {
    const c: Record<HoTrigger, number> = {
      A3_TTT: 0, E2_RIC_CONTROL: 0, MANUAL: 0, UNKNOWN: 0,
    };
    for (const e of events) c[e.trigger]++;
    return c;
  }, [events]);

  const sankeyData = useMemo(() => {
    const nodeMap = new Map<string, { id: string }>();
    const linkMap = new Map<string, number>();

    for (const e of events) {
      const sourceCell = e.source_cell?.trim();
      const targetCell = e.target_cell?.trim();
      if (
        !sourceCell || !targetCell ||
        sourceCell === 'unknown' || targetCell === 'unknown' ||
        sourceCell === targetCell
      ) {
        continue;
      }

      // d3-sankey cannot render directed cycles. HO traffic can legitimately
      // bounce both ways, so render it as source-side cells flowing into
      // target-side cells instead of reusing the same node id on both sides.
      const source = sourceNodeId(sourceCell);
      const target = targetNodeId(targetCell);
      nodeMap.set(source, { id: source });
      nodeMap.set(target, { id: target });

      const k = `${source}>>${target}`;
      linkMap.set(k, (linkMap.get(k) || 0) + 1);
    }
    if (linkMap.size === 0) return null;

    const nodes = Array.from(nodeMap.values());
    const links = Array.from(linkMap.entries()).map(([k, value]) => {
      const [source, target] = k.split('>>');
      return { source, target, value };
    });

    return { nodes, links };
  }, [events]);

  return (
    <section style={{ marginBottom: 24 }}>
      <h2 style={{
        margin: 0, color: C_TEXT, fontSize: 14, fontWeight: 600,
        marginBottom: 12,
      }}>
        🔁 Handover Map （過去 {windowSec}s）
      </h2>

      <div style={{
        display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 12,
      }}>
        {/* Sankey or fallback */}
        <div style={{
          background: C_CARD, border: `1px solid ${C_BORDER}`, borderRadius: 8,
          padding: 12, minHeight: 280,
        }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            marginBottom: 8,
          }}>
            <span style={{ fontSize: 12, color: C_TEXT, fontWeight: 600 }}>
              Source → Target flow
            </span>
            <span style={{ fontSize: 11, color: C_MUTED }}>
              total {events.length}
            </span>
          </div>
          {sankeyData ? (
            <div style={{ height: 240 }}>
              <ResponsiveSankey
                data={sankeyData}
                margin={{ top: 10, right: 80, bottom: 10, left: 80 }}
                align="justify"
                colors={{ scheme: 'category10' }}
                nodeOpacity={1}
                nodeThickness={14}
                nodeBorderWidth={0}
                linkOpacity={0.5}
                linkContract={3}
                enableLinkGradient
                labelTextColor={C_TEXT}
                theme={{
                  background: 'transparent',
                  text: { fill: C_TEXT, fontSize: 11 },
                  tooltip: {
                    container: {
                      background: '#0b1220', color: C_TEXT,
                      fontSize: 11, border: `1px solid ${C_BORDER}`,
                    },
                  },
                }}
              />
            </div>
          ) : (
            <div style={{
              height: 240,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: C_MUTED, fontSize: 11, textAlign: 'center', padding: 16,
            }}>
              過去 {windowSec}s 內無 Handover 事件。
            </div>
          )}
          <div style={{
            display: 'flex', gap: 12, marginTop: 8,
            fontSize: 11, color: C_MUTED, justifyContent: 'center',
          }}>
            {(Object.keys(counts) as HoTrigger[]).map(t => (
              <span key={t} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{
                  display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                  background: TRIG_COLORS[t],
                }} />
                {t}: {counts[t]}
              </span>
            ))}
          </div>
        </div>

        {/* Recent events list */}
        <div style={{
          background: C_CARD, border: `1px solid ${C_BORDER}`, borderRadius: 8,
          padding: 12, maxHeight: 280, overflowY: 'auto',
        }}>
          <div style={{ fontSize: 12, color: C_TEXT, fontWeight: 600, marginBottom: 8 }}>
            Recent events
          </div>
          {events.length === 0 ? (
            <div style={{ color: C_MUTED, fontSize: 11 }}>(no HO triggered in window)</div>
          ) : (
            <table style={{ fontSize: 10, width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C_BORDER}`, color: C_MUTED }}>
                  <th style={{ textAlign: 'left', padding: 4 }}>t</th>
                  <th style={{ textAlign: 'left', padding: 4 }}>UE</th>
                  <th style={{ textAlign: 'left', padding: 4 }}>trigger</th>
                  <th style={{ textAlign: 'left', padding: 4 }}>via</th>
                </tr>
              </thead>
              <tbody>
                {events.slice(0, 20).map((e, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #1f2937' }}>
                    <td style={{ padding: 4, color: C_MUTED, fontFamily: 'monospace' }}>
                      {new Date(e.ts_ms).toLocaleTimeString('en-GB', { hour12: false })}
                    </td>
                    <td style={{ padding: 4, color: C_TEXT, fontFamily: 'monospace' }}>
                      {e.ue_id || '—'}
                    </td>
                    <td style={{ padding: 4, color: TRIG_COLORS[e.trigger], fontWeight: 600 }}>
                      {e.trigger}
                    </td>
                    <td style={{ padding: 4, color: C_MUTED }}>
                      {e.service}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </section>
  );
}
