import { ServingStrip } from '@/components/charts/ServingStrip';
import { TimeSeriesChart } from '@/components/charts/TimeSeriesChart';
import type { Pt } from '@/types/telemetry';

interface M { key: string; label: string; unit: string; min?: number; max?: number; points: Pt[]; }
/** 選中 UE 的全指標時序:一指標一圖(不做雙軸) + serving 色帶 */
export function UeDetail({ id, metrics, serving, color, xLabels, onClose }: { id: string; metrics: readonly M[]; serving: { x: number; cell: string }[]; color: Record<string, string>; xLabels: number[]; onClose: () => void }) {
  return (
    <div className="ue-detail">
      <header><b className="mono">{id}</b><span className="muted">serving cell</span><div className="strip"><ServingStrip strip={serving} color={color} height={10} /></div><button className="ghost" onClick={onClose}>關閉</button></header>
      <div className="ue-detail-grid">{metrics.map((m) => (
        <div key={m.key} className="mini-panel"><div className="mini-h">{m.label}{m.unit && <span className="muted"> ({m.unit})</span>}</div>
          <TimeSeriesChart series={[{ key: m.key, label: m.label, color: 'var(--cyan)', points: m.points }]} unit="" height={120} yMin={m.min} yMax={m.max} xLabels={xLabels} legend={false} /></div>))}</div>
    </div>
  );
}
