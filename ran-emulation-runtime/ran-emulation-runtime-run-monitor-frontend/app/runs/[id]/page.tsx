'use client';
import { useParams } from 'next/navigation';
import { E2PlaneStatus } from '@/components/run-dashboard/E2PlaneStatus';
import { HandoverList } from '@/components/run-dashboard/HandoverList';
import { KpmCellTable } from '@/components/run-dashboard/KpmCellTable';
import { KpmUeTable } from '@/components/run-dashboard/KpmUeTable';
import { RicCommandTimeline } from '@/components/run-dashboard/RicCommandTimeline';
import { Section } from '@/components/run-dashboard/Section';
import { useRunDashboardPage } from '@/hooks/feature/useRunDashboardPage';

export default function RunDashboardPage() {
  const { id } = useParams<{ id: string }>();
  const p = useRunDashboardPage(id);
  if (p.error) return <p className="err page">{p.error.message}</p>;
  if (!p.run) return <p className="muted page">載入 run…</p>;
  const l = p.latest;
  return (
    <section className="page wide">
      <header className="runhead">
        <h1>{p.sceneName || p.run.f_scene_uuid}</h1>
        <span className={`pill ${p.run.status}`}>{p.run.status}</span>
        <span className="mono muted">{p.run.scene_run_uuid}</span>
        {l && <span className="muted">sim-time {(l.sim_time_ms / 1000).toFixed(0)}s · 視窗 {p.samples.length}{p.live ? ' · 每 3 s 更新' : ''}</span>}
      </header>
      <div className="grid2">
        <Section title="① Full KPM(per-cell)" sub={l ? `window ${l.window_index}` : undefined}>
          <KpmCellTable latest={l} series={p.cellSeries} ueCount={p.cellUeCount} />
          <button className="link" onClick={() => p.setExpandedUe(!p.expandedUe)}>{p.expandedUe ? '收起 per-UE' : `展開 per-UE(${l ? Object.keys(l.per_ue).length : 0})`}</button>
          {p.expandedUe && <KpmUeTable latest={l} />}
        </Section>
        <Section title="② RIC 命令狀況" sub={`${p.controls.length} 筆`}><RicCommandTimeline items={p.commandImpact} /></Section>
        <Section title="③ Cell 狀態" sub={l ? `${Object.keys(l.per_cell).length} cells` : undefined}>
          {l ? <ul className="cells">{Object.entries(l.per_cell).map(([c, k]) => <li key={c}><b className="mono">{c}</b> PRB {k.prb_pct_dl.toFixed(1)}% · UE {p.cellUeCount[c] ?? 0}</li>)}</ul> : <p className="muted">—</p>}
        </Section>
        <Section title="④ E2 面狀態"><E2PlaneStatus run={p.run} e2={p.e2} du={p.duTick} /></Section>
      </div>
      <Section title="換手 / RLF" sub={`${p.handovers.length} 筆`} defaultOpen={false}><HandoverList items={p.handovers} /></Section>
      <Section title="設定快照(唯讀)" defaultOpen={false}><pre className="mono small">{JSON.stringify({ mode: p.run.mode, speed_x: p.run.speed_x, sim_dt_ms: p.run.sim_dt_ms, duration_sec: p.run.duration_sec, cache_path: p.run.cache_path, notes: p.run.notes }, null, 2)}</pre></Section>
      <Section title="起停紀錄" defaultOpen={false}><ul className="cells">{p.launches.map((x) => <li key={x.launch_request_uuid}><span className="mono">{x.launch_request_created_at.slice(11, 19)}</span> {x.action} → {x.status}</li>)}</ul></Section>
    </section>
  );
}
