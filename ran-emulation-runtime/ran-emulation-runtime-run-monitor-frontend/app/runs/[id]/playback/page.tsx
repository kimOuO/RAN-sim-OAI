'use client';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { BarChart } from '@/components/charts/BarChart';
import { Panel } from '@/components/dashboard/Panel';
import { UeSmallMultiples } from '@/components/dashboard/UeSmallMultiples';
import { useRunDashboardPage } from '@/hooks/feature/useRunDashboardPage';
import { usePlayback3d } from '@/hooks/feature/usePlayback3d';
import { LiveScene3D } from '@/components/scene3d/LiveScene3D';
import { fmtSimTime } from '@/hooks/feature/kpmDerive';

export default function PlaybackPage() {
  const { id } = useParams<{ id: string }>();
  const p = useRunDashboardPage(id);
  const idx0 = p.selectedWindow ?? Math.max(0, p.all.length - 1);
  const v = usePlayback3d(p.run?.f_scene_uuid, p.all, idx0, p.setSelectedWindow);
  if (!p.all.length) return <p className="muted">{p.status === 'loading' ? '載入…' : '本 run 沒有封存視窗'}</p>;
  const idx = p.selectedWindow ?? p.all.length - 1; const w = p.all[idx];
  const bars = p.cells.filter((c) => w.per_cell[c]).map((c) => ({ label: c, value: w.per_cell[c].prb_pct_dl, color: p.color[c], sub: `${Object.values(w.per_ue).filter((u) => u.serving_cell === c).length} UE` }));
  return (
    <>
      <header className="runhead"><div><div className="crumbs"><Link href="/runs">Runs</Link> / <Link href={`/runs/${id}`}>{p.sceneName}</Link></div><h1>回放</h1></div></header>
      <div className="card"><label className="slider"><span><button className="mini" onClick={v.toggle}>{v.playing ? '❚❚' : '▶'}</button> <select value={v.rate} onChange={(e) => v.setRate(Number(e.target.value))}>{[1, 5, 10, 30].map((r) => <option key={r} value={r}>{r} 窗/秒</option>)}</select> 視窗 {w.window_index} · sim-time {fmtSimTime(w.sim_time_ms / 1000)}{w.scene_t_sec != null ? ` · 劇本 ${fmtSimTime(w.scene_t_sec)}` : ''} · {Object.keys(w.per_ue).length} UE</span>
        <input type="range" min={0} max={p.all.length - 1} value={idx} onChange={(e) => p.setSelectedWindow(Number(e.target.value))} /></label></div>
      {v.tree && <div className="live3d playback3d">
        {v.hasSceneTime ? <LiveScene3D tree={v.tree} simNow={v.simNow} ueState={v.ueState} flashes={v.flashes} color={v.color} selected={v.selected} onSelect={v.setSelected} showLabels={false} />
          : <p className="muted pad">這個視窗沒有劇本時間(2026-09-17 之前封存的資料),無法畫 UE 位置。</p>}
      </div>}
      <div className="grid">
        <Panel title="cell 負載(此視窗)" span={4}><BarChart bars={bars} unit="%" max={100} /></Panel>
        <Panel title="UE(此視窗)" span={8}><UeSmallMultiples items={p.ueSmall.map((u) => ({ ...u, last: w.per_ue[u.id] ?? null }))} color={p.color} selected={p.selectedUe} onSelect={p.setSelectedUe} /></Panel>
      </div>
    </>
  );
}
