'use client';
import { useParams } from 'next/navigation';
import { useRunDashboardPage } from '@/hooks/feature/useRunDashboardPage';

export default function EventsPage() {
  const { id } = useParams<{ id: string }>();
  const p = useRunDashboardPage(id);
  const rows = [
    ...p.launches.map((x) => ({ at: x.launch_request_created_at, kind: 'run', text: `${x.action} → ${x.status}` })),
    ...p.handovers.map((h) => ({ at: h.run_handover_event_created_at, kind: h.outcome === 'RLF' ? 'rlf' : 'ho', text: `${h.ue_id} ${h.source_cell || '—'} → ${h.target_cell || '—'} (${h.outcome})` })),
    ...p.controls.map((c) => ({ at: c.run_control_event_created_at, kind: 'ric', text: `${c.action_type} ${c.target} (${c.outcome})` })),
  ].sort((a, b) => b.at.localeCompare(a.at));
  return (
    <section className="page">
      <h1>事件流 · {p.sceneName}</h1>
      <ul className="events">{rows.map((r, i) => <li key={i} className={r.kind}><span className="mono">{r.at.slice(0, 19).replace('T', ' ')}</span><span className="pill">{r.kind}</span>{r.text}</li>)}</ul>
      {!rows.length && <p className="muted">無事件</p>}
    </section>
  );
}
