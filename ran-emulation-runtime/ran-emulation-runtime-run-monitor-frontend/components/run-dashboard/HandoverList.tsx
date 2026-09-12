import type { HandoverEvent } from '@/types/telemetry';

export function HandoverList({ items, limit = 30 }: { items: HandoverEvent[]; limit?: number }) {
  const rows = [...items].sort((a, b) => b.run_handover_event_created_at.localeCompare(a.run_handover_event_created_at)).slice(0, limit);
  if (!rows.length) return <p className="muted">無換手 / RLF 事件</p>;
  return (
    <table>
      <thead><tr><th>時間</th><th>UE</th><th>來源</th><th>目標</th><th>結果</th><th>觸發</th></tr></thead>
      <tbody>{rows.map((h) => (
        <tr key={h.run_handover_event_uuid}><td className="mono">{h.run_handover_event_created_at.slice(11, 19)}</td><td className="mono">{h.ue_id}</td><td className="mono">{h.source_cell || '—'}</td><td className="mono">{h.target_cell || '—'}</td>
          <td><span className={`pill ${h.outcome === 'RLF' ? 'poor' : h.outcome === 'DONE' || h.outcome === 'PREP' ? 'good' : 'fair'}`}>{h.outcome}</span></td>
          <td className="muted">{String(h.detail?.trigger ?? h.detail?.reason ?? '')}</td></tr>
      ))}</tbody>
    </table>
  );
}
