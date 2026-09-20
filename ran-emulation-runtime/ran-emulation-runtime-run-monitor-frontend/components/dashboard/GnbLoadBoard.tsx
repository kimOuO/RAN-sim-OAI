import { Gauge } from '@/components/charts/Gauge';
import type { KpmSample } from '@/types/telemetry';
/** PRB 使用率:gNB 一列,列首是 gNB 平均,後面每個 cell 一個圓環 */
export function GnbLoadBoard({ groups, latest, color, ueCount, metric = 'prb_pct_dl', label = 'PRB DL' }: { groups: { gnb: string; cells: string[] }[]; latest: KpmSample | null; color: Record<string, string>; ueCount: Record<string, number>; metric?: 'prb_pct_dl' | 'prb_pct_ul'; label?: string }) {
  if (!latest) return <p className="muted">尚無資料</p>;
  return (
    <div className="gnb-board">{groups.map((g) => { const vals = g.cells.map((c) => latest.per_cell[c]?.[metric] ?? null).filter((v): v is number => v != null); const avg = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null; return (
      <div key={g.gnb} className="gnb-row">
        <div className="gnb-head"><Gauge value={avg} label={g.gnb} sub={`gNB · ${g.cells.length} cell · ${g.cells.reduce((n, c) => n + (ueCount[c] ?? 0), 0)} UE`} color="var(--cyan)" /></div>
        <div className="gnb-cells">{g.cells.map((c) => <Gauge key={c} value={latest.per_cell[c]?.[metric] ?? null} label={c} sub={`${ueCount[c] ?? 0} UE · ${label}`} color={color[c] ?? '#888'} />)}</div>
      </div>); })}</div>
  );
}
