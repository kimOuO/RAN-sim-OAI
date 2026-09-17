'use client';
import Link from 'next/link';
import { RunSubNav } from '@/components/dashboard/RunSubNav';
import { useParams } from 'next/navigation';
import { useState } from 'react';
import { useRunDashboardPage } from '@/hooks/feature/useRunDashboardPage';

const KINDS = ['run', 'ho', 'rlf', 'ric'] as const;
export default function EventsPage() {
  const { id } = useParams<{ id: string }>();
  const p = useRunDashboardPage(id);
  const [on, setOn] = useState<Record<string, boolean>>({ run: true, ho: true, rlf: true, ric: true });
  const rows = [
    ...p.launches.map((x) => ({ at: x.launch_request_created_at, kind: 'run', text: `${x.action} → ${x.status}`, sim: null as number | null })),
    ...p.handovers.map((h) => ({ at: h.run_handover_event_created_at, kind: h.outcome === 'RLF' ? 'rlf' : 'ho', text: `${h.ue_id}  ${h.source_cell || '—'} → ${h.target_cell || '—'}  (${h.outcome})`, sim: h.at_sim_ms })),
    ...p.controls.map((c) => ({ at: c.run_control_event_created_at, kind: 'ric', text: `${c.action_type} ${c.target} (${c.outcome})`, sim: c.at_sim_ms })),
  ].filter((r) => on[r.kind]).sort((a, b) => b.at.localeCompare(a.at));
  return (
    <>
      <header className="runhead"><div><div className="crumbs"><Link href="/runs">Runs</Link> / <Link href={`/runs/${id}`}>{p.sceneName}</Link></div><h1>事件流</h1></div><span className="muted">{rows.length} 筆</span><span className="sp" /><RunSubNav id={id} /></header>
      <div className="toolbar"><div className="chips">{KINDS.map((k) => <button key={k} className={`chip ${k} ${on[k] ? 'on' : ''}`} onClick={() => setOn({ ...on, [k]: !on[k] })}>{k}</button>)}</div></div>
      <div className="card"><ul className="events">{rows.map((r, i) => <li key={i} className={r.kind}><span className="mono">{r.at.slice(5, 19).replace('T', ' ')}</span><span className="pill">{r.kind}</span><span className="mono muted">{r.sim != null ? `${(r.sim / 1000).toFixed(0)}s` : ''}</span>{r.text}</li>)}</ul>
        {!rows.length && <p className="muted">無事件</p>}</div>
    </>
  );
}
