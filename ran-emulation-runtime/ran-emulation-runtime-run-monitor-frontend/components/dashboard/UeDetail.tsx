import { ServingStrip } from '@/components/charts/ServingStrip';
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart';
import type { Pt, UeKpm } from '@/types/telemetry';

interface M { key: string; label: string; unit: string; min?: number; max?: number; points: Pt[]; }
/** 選中 UE 的全指標時序:一指標一圖(不做雙軸) + serving 色帶 */
export function UeDetail({ id, metrics, serving, color, xLabels, last, onClose }: { id: string; metrics: readonly M[]; serving: { x: number; cell: string }[]; color: Record<string, string>; xLabels: number[]; last: UeKpm | null; onClose: () => void }) {
  return (
    <div className="ue-detail">
      <header><b className="mono">{id}</b><span className="muted">serving cell</span><div className="strip"><ServingStrip strip={serving} color={color} height={10} /></div><button className="ghost" onClick={onClose}>關閉</button></header>
      {last && <div className="ue-now"><span>serving <b className="mono" style={{ color: color[last.serving_cell] }}>{last.serving_cell}</b></span><span>rank <b>{last.mimo_rank}</b></span><span>5QI <b>{last.qos_5qi}</b></span><span>PRB DL/UL <b>{last.rb_width_dl}</b>/<b>{last.rb_width_ul ?? '—'}</b></span><span>UL SINR <b>{last.ul_sinr_db != null ? last.ul_sinr_db.toFixed(1) : '—'}</b> dB</span><span>波束 <b>{last.beam_id != null ? `#${last.beam_id}` : '—'}</b></span><span>每層 SINR {last.sinr_layers_json?.length ? last.sinr_layers_json.map((v, i) => <b key={i} className="mono" style={{ marginRight: 4 }}>L{i}:{v.toFixed(1)}</b>) : <span className="muted">—</span>}</span>
        <span className="nbrs">鄰區 {last.neighbor_cells_json?.length ? last.neighbor_cells_json.map((n) => <span key={n.cell_id} className="nbr"><i style={{ background: color[n.cell_id] ?? '#666' }} /><span className="mono">{n.cell_id}</span> {n.rsrp_dbm.toFixed(1)} dBm{n.rsrq_db ? ` / ${n.rsrq_db.toFixed(1)} dB` : ''}</span>) : <span className="muted">—</span>}</span></div>}
      <div className="ue-detail-grid">{metrics.map((m) => (
        <div key={m.key} className="mini-panel"><div className="mini-h">{m.label}{m.unit && <span className="muted"> ({m.unit})</span>}</div>
          <TimeSeriesChart series={[{ key: m.key, label: m.label, color: 'var(--cyan)', points: m.points }]} unit="" height={120} yMin={m.min} yMax={m.max} xLabels={xLabels} legend={false} /></div>))}</div>
    </div>
  );
}
