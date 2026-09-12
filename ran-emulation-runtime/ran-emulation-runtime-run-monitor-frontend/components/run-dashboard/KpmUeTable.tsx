import { UE_METRICS } from '@/config';
import type { KpmSample } from '@/types/telemetry';

const quality = (sinr: number) => (sinr >= 10 ? 'good' : sinr >= 0 ? 'fair' : 'poor');
export function KpmUeTable({ latest }: { latest: KpmSample | null }) {
  if (!latest) return null;
  const rows = Object.entries(latest.per_ue).sort(([a], [b]) => a.localeCompare(b));
  return (
    <table>
      <thead><tr><th>UE</th><th>serving</th>{UE_METRICS.map((m) => <th key={m.key}>{m.label}</th>)}<th>quality</th></tr></thead>
      <tbody>{rows.map(([u, k]) => (
        <tr key={u}><td className="mono">{u}</td><td className="mono">{k.serving_cell}</td>
          {UE_METRICS.map((m) => <td key={m.key} className="num">{Number(k[m.key] ?? 0).toFixed(m.digits)}{m.unit}</td>)}
          <td><span className={`pill ${quality(k.sinr_db)}`}>{quality(k.sinr_db)}</span></td></tr>
      ))}</tbody>
    </table>
  );
}
