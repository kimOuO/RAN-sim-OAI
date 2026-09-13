'use client';
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart';
import { Panel } from '@/components/dashboard/Panel';
import { useComparePage } from '@/hooks/feature/useComparePage';

export default function ComparePage() {
  const p = useComparePage();
  return (
    <>
      <header className="pagehead"><h1>多 run 對照</h1><span className="muted">最多 4 個 run,同指標同圖,x = sim-time 視窗序</span></header>
      <div className="card picker">{p.candidates.map(({ run, label }) => { const on = p.picked.includes(run.scene_run_uuid); return (
        <button key={run.scene_run_uuid} className={`chip ${on ? 'on' : ''}`} style={on ? { borderColor: p.colorOf(run.scene_run_uuid), color: p.colorOf(run.scene_run_uuid) } : undefined} onClick={() => p.toggle(run.scene_run_uuid)}>{label} <span className="mono muted">{run.scene_run_uuid.slice(-4)}</span></button>); })}
        {!p.candidates.length && <span className="muted">沒有可比的 run</span>}</div>
      {p.picked.length > 0 && (
        <div className="grid">
          <Panel title="平均 PRB DL" span={6}><TimeSeriesChart series={p.charts.prb} unit="%" yMin={0} yMax={100} /></Panel>
          <Panel title="Σ DL 吞吐" span={6}><TimeSeriesChart series={p.charts.thp} yMin={0} digits={2} /></Panel>
          <Panel title="平均 SINR" span={4}><TimeSeriesChart series={p.charts.sinr} yMin={-10} yMax={40} /></Panel>
          <Panel title="附著 UE 數" span={4}><TimeSeriesChart series={p.charts.ue} yMin={0} digits={0} /></Panel>
          <Panel title="平均 MCS" span={4}><TimeSeriesChart series={p.charts.mcs} yMin={0} yMax={28} /></Panel>
        </div>)}
    </>
  );
}
