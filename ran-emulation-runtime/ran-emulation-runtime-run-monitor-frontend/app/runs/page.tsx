'use client';
import Link from 'next/link';
import { useRunListPage } from '@/hooks/feature/useRunListPage';

export default function RunsPage() {
  const p = useRunListPage();
  return (
    <section className="page">
      <header className="pagehead"><h1>Runs</h1><label><input type="checkbox" checked={p.onlyActive} onChange={(e) => p.setOnlyActive(e.target.checked)} /> 只看執行中</label>
        {p.duTick && <span className="muted">DU:tick {p.duTick.tick_count} · {p.duTick.is_running ? `達成 ${p.duTick.achieved_speed_x.toFixed(2)}×` : 'idle'}</span>}</header>
      {p.error && <p className="err">{p.error.message}</p>}
      <table>
        <thead><tr><th>狀態</th><th>場景</th><th>模式</th><th>倍速</th><th>sim_dt</th><th>時長</th><th>開始</th><th>結束</th><th></th></tr></thead>
        <tbody>{p.rows.map(({ run: r, sceneName }) => (
          <tr key={r.scene_run_uuid} className={r.status}>
            <td><span className={`pill ${r.status}`}>{r.status}</span></td><td><Link href={`/runs/${r.scene_run_uuid}`}>{sceneName}</Link></td><td>{r.mode}</td>
            <td className="num">{r.speed_x}×</td><td className="num">{r.sim_dt_ms} ms</td><td className="num">{r.duration_sec}s</td>
            <td className="mono">{r.started_at?.slice(0, 19).replace('T', ' ') ?? '—'}</td><td className="mono">{r.stopped_at?.slice(0, 19).replace('T', ' ') ?? '—'}</td>
            <td><Link href={`/runs/${r.scene_run_uuid}/events`}>events</Link> · <Link href={`/runs/${r.scene_run_uuid}/playback`}>playback</Link></td>
          </tr>
        ))}</tbody>
      </table>
      {p.status === 'loading' && !p.rows.length && <p className="muted">載入中…</p>}
    </section>
  );
}
