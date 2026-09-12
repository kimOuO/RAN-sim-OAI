'use client';
import { useParams } from 'next/navigation';
import { KpmCellTable } from '@/components/run-dashboard/KpmCellTable';
import { KpmUeTable } from '@/components/run-dashboard/KpmUeTable';
import { useRunDashboardPage } from '@/hooks/feature/useRunDashboardPage';

export default function PlaybackPage() {
  const { id } = useParams<{ id: string }>();
  const p = useRunDashboardPage(id);
  if (!p.samples.length) return <p className="muted page">{p.status === 'loading' ? '載入…' : '本 run 沒有封存視窗'}</p>;
  const idx = p.selectedWindow ?? p.samples.length - 1;
  return (
    <section className="page wide">
      <h1>回放 · {p.sceneName}</h1>
      <label className="slider">視窗 {idx} / {p.samples.length - 1} · sim-time {(p.samples[idx].sim_time_ms / 1000).toFixed(0)}s
        <input type="range" min={0} max={p.samples.length - 1} value={idx} onChange={(e) => p.setSelectedWindow(Number(e.target.value))} /></label>
      <KpmCellTable latest={p.samples[idx]} series={p.cellSeries} ueCount={p.cellUeCount} />
      <KpmUeTable latest={p.samples[idx]} />
    </section>
  );
}
