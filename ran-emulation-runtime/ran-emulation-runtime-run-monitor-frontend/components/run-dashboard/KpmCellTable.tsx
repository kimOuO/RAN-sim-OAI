import { Sparkline } from '@/components/charts/Sparkline';
import { CELL_METRICS } from '@/config';
import type { KpmSample } from '@/types/telemetry';

export function KpmCellTable({ latest, series, ueCount }: { latest: KpmSample | null; series: Record<string, { t: number; v: number }[]>; ueCount: Record<string, number> }) {
  if (!latest) return <p className="muted">尚無封存視窗</p>;
  return (
    <table>
      <thead><tr><th>cell</th>{CELL_METRICS.map((m) => <th key={m.key}>{m.label}</th>)}<th>UE</th><th>PrbTotDl 走勢</th></tr></thead>
      <tbody>{Object.entries(latest.per_cell).map(([c, k]) => (
        <tr key={c}><td className="mono">{c}</td>{CELL_METRICS.map((m) => <td key={m.key} className="num">{(k[m.key] ?? 0).toFixed(m.digits)}{m.unit}</td>)}
          <td className="num">{ueCount[c] ?? 0}</td><td><Sparkline points={series[c] ?? []} unit="%" yMin={0} yMax={100} /></td></tr>
      ))}</tbody>
    </table>
  );
}
