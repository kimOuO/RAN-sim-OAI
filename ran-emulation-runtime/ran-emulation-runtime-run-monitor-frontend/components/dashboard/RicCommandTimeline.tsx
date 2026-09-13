import type { ControlEvent } from '@/types/telemetry';
export function RicCommandTimeline({ items }: { items: { event: ControlEvent; prbBefore: number | null; prbAfter: number | null }[] }) {
  if (!items.length) return <div className="empty-state"><b>尚無 RIC 命令</b><span className="muted">E2 連上 RIC 且 xApp 下發後,命令會在這裡依時間排列,並顯示落地前後的 cell 負載變化。</span></div>;
  return (
    <ul className="cmd-list">{items.map(({ event: e, prbBefore, prbAfter }) => { const ok = e.outcome === 'ACK' || e.outcome === 'success'; const d = prbBefore != null && prbAfter != null ? prbAfter - prbBefore : null; return (
      <li key={e.run_control_event_uuid}><span className={`dot ${ok ? 'good' : e.outcome === 'pending' ? 'warning' : 'critical'}`} />
        <span className="mono">{(e.at_sim_ms / 1000).toFixed(0)}s</span><b className="mono">{e.action_type}</b><span className="mono muted">→ {e.target}</span>
        <span className="sp" /><span className="muted">{e.landing_latency_ms != null ? `${e.landing_latency_ms} ms` : ''}</span>
        {d != null && <span className={d < 0 ? 'down' : 'up'}>PRB {prbBefore!.toFixed(1)}% → {prbAfter!.toFixed(1)}%</span>}</li>); })}</ul>
  );
}
