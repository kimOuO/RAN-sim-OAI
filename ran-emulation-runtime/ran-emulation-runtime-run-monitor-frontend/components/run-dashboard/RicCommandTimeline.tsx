import type { ControlEvent } from '@/types/telemetry';

export function RicCommandTimeline({ items }: { items: { event: ControlEvent; prbBefore: number | null; prbAfter: number | null }[] }) {
  if (!items.length) return <p className="muted">本 run 沒有 RIC 命令(RIC 未連線時為空)</p>;
  return (
    <table>
      <thead><tr><th>sim-time</th><th>來源</th><th>類型</th><th>目標</th><th>落地</th><th>延遲</th><th>PrbTotDl 前 → 後</th></tr></thead>
      <tbody>{items.map(({ event: e, prbBefore, prbAfter }) => (
        <tr key={e.run_control_event_uuid}><td className="num">{(e.at_sim_ms / 1000).toFixed(1)}s</td><td>{e.source}</td><td className="mono">{e.action_type}</td><td className="mono">{e.target}</td>
          <td><span className={`pill ${e.outcome === 'ACK' || e.outcome === 'success' ? 'good' : e.outcome === 'pending' ? 'fair' : 'poor'}`}>{e.outcome}</span></td>
          <td className="num">{e.landing_latency_ms ?? '—'}{e.landing_latency_ms != null ? 'ms' : ''}</td>
          <td className="num">{prbBefore == null || prbAfter == null ? '—' : `${prbBefore.toFixed(1)}% → ${prbAfter.toFixed(1)}%`}</td></tr>
      ))}</tbody>
    </table>
  );
}
