import type { ControlEvent } from '@/types/telemetry';
import { controlOrigin, controlOriginLabel, ctrlOk } from '@/hooks/feature/controlEvents';
export function RicCommandTimeline({ items }: { items: { event: ControlEvent; prbBefore: number | null; prbAfter: number | null }[] }) {
  if (!items.length) return <div className="empty-state"><b>尚無控制指令或自主事件</b><span className="muted">RIC / xApp 下發指令與 RAN 自主 SON 行為會依來源標示，並顯示執行前後的 cell 負載變化。</span></div>;
  return (
    <ul className="cmd-list">{items.map(({ event: e, prbBefore, prbAfter }) => { const ok = ctrlOk(e.outcome); const d = prbBefore != null && prbAfter != null ? prbAfter - prbBefore : null; return (
      <li key={e.run_control_event_uuid}><span className={`dot ${ok ? 'good' : e.outcome === 'pending' ? 'warning' : 'critical'}`} />
        <span className="mono">{(e.at_sim_ms / 1000).toFixed(0)}s</span><span className={`tag ${controlOrigin(e.source)}`}>{controlOriginLabel(e.source)}</span>
        <span className="mono muted">{e.source}</span><b className="mono">{e.action_type}</b><span className="mono muted">→ {e.target}</span><span>{e.outcome}</span>
        <span className="sp" /><span className="muted">{e.landing_latency_ms != null ? `${e.landing_latency_ms} ms` : ''}</span>
        {d != null && <span className={d < 0 ? 'down' : 'up'}>PRB {prbBefore!.toFixed(1)}% → {prbAfter!.toFixed(1)}%</span>}</li>); })}</ul>
  );
}
