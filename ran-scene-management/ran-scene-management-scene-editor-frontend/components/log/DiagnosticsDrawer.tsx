'use client';

import { useState } from 'react';
import { ActivityTimeline } from './ActivityTimeline';
import { ServiceCategoryHeatmap } from './ServiceCategoryHeatmap';
import { TopCategoriesPanel } from './TopCategoriesPanel';
import { StatsStrip } from './StatsStrip';
import { LogFilterBar } from './LogFilterBar';
import { RanLogTable } from './RanLogTable';
import { E2EventTimeline } from './E2EventTimeline';
import type { RingEntry, LogFilters } from '@/lib/logStats';

interface Props {
  logs: RingEntry[];
  filteredLogs: RingEntry[];
  filters: LogFilters;
  onFiltersChange: (f: LogFilters) => void;
  autoScroll: boolean;
  onAutoScrollChange: (b: boolean) => void;
  stats: any;
  now: number;
}

type Section = 'message_density' | 'raw_logs' | 'e2_events' | null;

const C_BG = '#0b1220';
const C_CARD = '#111827';
const C_BORDER = '#374151';
const C_TEXT = '#cbd5e1';
const C_MUTED = '#6b7280';

export function DiagnosticsDrawer(props: Props) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<Section>(null);

  const togglePanel = (s: Section) => setActive(prev => (prev === s ? null : s));

  return (
    <div style={{
      background: C_BG, border: `1px solid ${C_BORDER}`,
      borderRadius: 10, marginTop: 24, overflow: 'hidden',
    }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%', padding: '12px 16px',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          background: 'transparent', border: 'none', color: C_TEXT,
          cursor: 'pointer', fontSize: 14, fontWeight: 600,
        }}
      >
        <span>⚙ Diagnostics（訊息密度、原始 log、E2 事件流）</span>
        <span style={{ fontSize: 11, color: C_MUTED }}>
          {open ? '▼ collapse' : '▶ expand'} · {props.logs.length} entries
        </span>
      </button>

      {open && (
        <div style={{ padding: '0 16px 16px' }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <PanelButton active={active === 'message_density'}
                         onClick={() => togglePanel('message_density')}>
              📊 Message Density
            </PanelButton>
            <PanelButton active={active === 'raw_logs'}
                         onClick={() => togglePanel('raw_logs')}>
              📝 Raw Logs
            </PanelButton>
            <PanelButton active={active === 'e2_events'}
                         onClick={() => togglePanel('e2_events')}>
              🛰 E2 Plane Events
            </PanelButton>
          </div>

          {active === 'message_density' && (
            <div style={{ background: C_CARD, padding: 12, borderRadius: 6 }}>
              <StatsStrip stats={props.stats} />
              <div style={{ marginTop: 12 }}>
                <ActivityTimeline logs={props.filteredLogs} now={props.now} />
              </div>
              <div style={{
                display: 'grid', gridTemplateColumns: '1fr 1fr',
                gap: 12, marginTop: 12,
              }}>
                <ServiceCategoryHeatmap logs={props.filteredLogs} now={props.now} />
                <TopCategoriesPanel logs={props.filteredLogs} now={props.now} />
              </div>
            </div>
          )}

          {active === 'raw_logs' && (
            <div style={{ background: C_CARD, padding: 12, borderRadius: 6 }}>
              <LogFilterBar
                filters={props.filters}
                onChange={props.onFiltersChange}
                autoScroll={props.autoScroll}
                onAutoScrollChange={props.onAutoScrollChange}
                matchedCount={props.filteredLogs.length}
                totalCount={props.logs.length}
              />
              <div style={{ marginTop: 8 }}>
                <RanLogTable entries={props.filteredLogs} autoScroll={props.autoScroll} />
              </div>
            </div>
          )}

          {active === 'e2_events' && (
            <div style={{ background: C_CARD, padding: 12, borderRadius: 6 }}>
              <E2EventTimeline />
            </div>
          )}

          {active === null && (
            <div style={{
              padding: 12, color: C_MUTED, fontSize: 12, textAlign: 'center',
            }}>
              Pick a panel above to inspect message-level diagnostics.
            </div>
          )}
        </div>
      )}
    </div>
  );
}


function PanelButton(props: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={props.onClick}
      style={{
        padding: '6px 12px', fontSize: 12,
        borderRadius: 4,
        background: props.active ? '#3b82f6' : 'transparent',
        color: props.active ? '#fff' : C_TEXT,
        border: `1px solid ${props.active ? '#3b82f6' : C_BORDER}`,
        cursor: 'pointer',
      }}
    >
      {props.children}
    </button>
  );
}
