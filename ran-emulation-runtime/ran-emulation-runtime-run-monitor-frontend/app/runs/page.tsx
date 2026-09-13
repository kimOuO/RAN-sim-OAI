'use client';
import Link from 'next/link';
import { StatTile } from '@/components/dashboard/StatTile';
import { useRunListPage } from '@/hooks/feature/useRunListPage';

const ORDER = ['running', 'ready', 'stopped', 'draft', 'pending', 'precomputing', 'failed'];
export default function RunsPage() {
  const p = useRunListPage();
  const link = p.e2?.sctp_link;
  return (
    <>
      <header className="pagehead"><h1>Runs</h1><span className="muted">{p.total} 個 run</span></header>
      <div className="stats">
        <StatTile label="執行中" value={p.counts.running ?? 0} digits={0} tone={p.counts.running ? 'good' : undefined} />
        <StatTile label="已完成" value={p.counts.stopped ?? 0} digits={0} />
        <StatTile label="DU 達成倍速" value={p.duTick?.is_running ? p.duTick.achieved_speed_x : null} unit="×" digits={2} foot={p.duTick ? `設定 ${p.duTick.sim_speed_x}× · tick ${p.duTick.tick_count}` : 'DU 無回應'} />
        <StatTile label="UE driver" value={p.ueDriver ? p.ueDriver.ue_count : null} unit=" UE" digits={0} foot={p.ueDriver ? `${p.ueDriver.scenario_id} · ${p.ueDriver.phase}` : '無回應'} />
        <StatTile label="E2 → RIC" value={null} tone={link?.connected ? 'good' : 'critical'} foot={link ? `${link.connected ? 'connected' : 'down'} · ${link.target_host}:${link.target_port}` : 'E2Adapter 無回應'} />
      </div>
      <div className="toolbar">
        <div className="chips"><button className={`chip ${p.statusFilter === 'all' ? 'on' : ''}`} onClick={() => p.setStatusFilter('all')}>全部 {p.total}</button>
          {ORDER.filter((s) => p.counts[s]).map((s) => <button key={s} className={`chip ${p.statusFilter === s ? 'on' : ''}`} onClick={() => p.setStatusFilter(s)}>{s} {p.counts[s]}</button>)}</div>
        <input placeholder="搜尋場景…" value={p.q} onChange={(e) => p.setQ(e.target.value)} />
      </div>
      {p.error && <p className="err">{p.error.message}</p>}
      <div className="card">
        <table>
          <thead><tr><th>狀態</th><th>場景</th><th>模式</th><th className="num">倍速</th><th className="num">sim_dt</th><th className="num">時長</th><th>開始</th><th>結束</th><th></th></tr></thead>
          <tbody>{p.rows.map(({ run: r, sceneName }) => (
            <tr key={r.scene_run_uuid}>
              <td><span className={`pill ${r.status}`}>{r.status}</span></td><td><Link href={`/runs/${r.scene_run_uuid}`}><b>{sceneName}</b></Link><div className="mono muted small">{r.scene_run_uuid.slice(-12)}</div></td><td>{r.mode}</td>
              <td className="num">{r.speed_x}×</td><td className="num">{r.sim_dt_ms} ms</td><td className="num">{(r.duration_sec / 3600).toFixed(1)} h</td>
              <td className="mono">{r.started_at?.slice(5, 19).replace('T', ' ') ?? '—'}</td><td className="mono">{r.stopped_at?.slice(5, 19).replace('T', ' ') ?? '—'}</td>
              <td className="links"><Link href={`/runs/${r.scene_run_uuid}`}>dashboard</Link><Link href={`/runs/${r.scene_run_uuid}/events`}>events</Link><Link href={`/runs/${r.scene_run_uuid}/playback`}>playback</Link></td>
            </tr>))}</tbody>
        </table>
        {p.status === 'loading' && !p.rows.length && <p className="muted">載入中…</p>}
      </div>
    </>
  );
}
