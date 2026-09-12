'use client';
import { Sparkline } from '@/components/charts/Sparkline';
import { useComparePage } from '@/hooks/feature/useComparePage';

export default function ComparePage() {
  const p = useComparePage();
  const cells = Array.from(new Set(p.picked.flatMap((id) => Object.keys(p.perRunCells[id] ?? {}))));
  return (
    <section className="page wide">
      <h1>並看(最多 4 個 run,PrbTotDl 依 sim-time 對齊)</h1>
      <ul className="picker">{p.candidates.map(({ run, label }) => <li key={run.scene_run_uuid}><label><input type="checkbox" checked={p.picked.includes(run.scene_run_uuid)} onChange={() => p.toggle(run.scene_run_uuid)} /> {label}</label></li>)}</ul>
      {cells.length > 0 && (
        <table><thead><tr><th>cell</th>{p.picked.map((id) => <th key={id}>{p.labelOf(id)}</th>)}</tr></thead>
          <tbody>{cells.map((c) => <tr key={c}><td className="mono">{c}</td>{p.picked.map((id) => <td key={id}><Sparkline points={p.perRunCells[id]?.[c] ?? []} unit="%" yMin={0} yMax={100} /></td>)}</tr>)}</tbody></table>
      )}
    </section>
  );
}
