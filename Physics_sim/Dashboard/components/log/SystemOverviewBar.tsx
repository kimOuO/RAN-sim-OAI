'use client';

import { useSystemOverview } from '@/hooks/feature/log/useSystemOverview';

const C_CARD = '#111827';
const C_BORDER = '#374151';
const C_TEXT = '#cbd5e1';
const C_MUTED = '#6b7280';
const C_OK = '#10b981';
const C_WARN = '#f59e0b';
const C_FAIL = '#ef4444';

export function SystemOverviewBar() {
  const o = useSystemOverview();

  const tickColor = !o.tick ? C_MUTED : (o.tick.is_running ? C_OK : C_FAIL);
  const e2Color = !o.e2.connected ? C_FAIL : (o.e2.setup_ok ? C_OK : C_WARN);
  const e2SilentRatio = o.e2.recv > 0 ? o.e2.sent / Math.max(o.e2.recv, 1) : Infinity;
  const e2Silent = o.e2.connected && e2SilentRatio > 100;

  const cellsColor = o.cells.total === 0 ? C_MUTED
    : o.cells.active === o.cells.total ? C_OK : C_WARN;
  const ueColor = o.ue.total === 0 ? C_MUTED
    : o.ue.connected === o.ue.total ? C_OK
    : o.ue.connected > 0 ? C_WARN : C_FAIL;

  return (
    <div style={{
      position: 'sticky', top: 0, zIndex: 20,
      background: '#0b1220', borderBottom: `1px solid ${C_BORDER}`,
      padding: '12px 0', marginBottom: 16,
    }}>
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12,
      }}>
        <KpiCard
          label="Sim Tick"
          dot={tickColor}
          headline={o.tick ? `sfn ${o.tick.sfn} · slot ${o.tick.slot}` : '—'}
          sub={o.tick ? `${o.tick.is_running ? 'running' : 'stopped'} · #${o.tick.tick_count}` : 'no data'}
        />
        <KpiCard
          label="E2 Link"
          dot={e2Color}
          headline={
            !o.e2.connected ? 'DISCONNECTED'
            : o.e2.setup_ok ? `up · sent ${o.e2.sent}` : 'connected · setup pending'
          }
          sub={
            e2Silent
              ? `⚠ silent peer (sent/recv ratio ${e2SilentRatio.toFixed(0)}:1)`
              : `recv ${o.e2.recv}`
          }
          subColor={e2Silent ? C_WARN : C_MUTED}
        />
        <KpiCard
          label="Cells"
          dot={cellsColor}
          headline={`${o.cells.active} / ${o.cells.total}`}
          sub={o.cells.active < o.cells.total ? `${o.cells.total - o.cells.active} inactive` : 'all active'}
        />
        <KpiCard
          label="UE"
          dot={ueColor}
          headline={`${o.ue.connected} / ${o.ue.total}`}
          sub={o.ue.total - o.ue.connected > 0
            ? `${o.ue.total - o.ue.connected} idle/stale`
            : 'all connected'}
        />
      </div>
    </div>
  );
}


interface KpiProps {
  label: string; dot: string; headline: string;
  sub: string; subColor?: string;
}
function KpiCard({ label, dot, headline, sub, subColor = C_MUTED }: KpiProps) {
  return (
    <div style={{
      background: C_CARD, border: `1px solid ${C_BORDER}`, borderRadius: 8,
      padding: 12,
    }}>
      <div style={{
        fontSize: 10, color: C_MUTED, textTransform: 'uppercase',
        letterSpacing: 0.6, marginBottom: 6,
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <span style={{
          display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
          background: dot, boxShadow: `0 0 6px ${dot}80`,
        }} />
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 700, color: C_TEXT, fontFamily: 'monospace' }}>
        {headline}
      </div>
      <div style={{ fontSize: 11, color: subColor, marginTop: 2 }}>
        {sub}
      </div>
    </div>
  );
}
