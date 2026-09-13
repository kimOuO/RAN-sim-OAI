'use client';
import { ServingStrip } from '@/components/charts/ServingStrip';
import { Sparkline } from '@/components/charts/Sparkline';
import type { Pt, UeKpm } from '@/types/telemetry';

interface Item { id: string; sinr: Pt[]; serving: { x: number; cell: string }[]; last: UeKpm | null; }
/** 一個個 UE:每個一張 SINR 迷你圖 + serving cell 色帶 + 當下值;點了看細節 */
export function UeSmallMultiples({ items, color, selected, onSelect }: { items: Item[]; color: Record<string, string>; selected: string | null; onSelect: (id: string) => void }) {
  if (!items.length) return <p className="muted">尚無 UE 資料</p>;
  return (
    <div className="ue-grid">{items.map((u) => { const c = u.last ? color[u.last.serving_cell] ?? '#888' : '#555'; const q = u.last ? (u.last.sinr_db >= 10 ? 'good' : u.last.sinr_db >= 0 ? 'warning' : 'critical') : ''; return (
      <button key={u.id} className={`ue-card ${selected === u.id ? 'sel' : ''}`} onClick={() => onSelect(u.id)}>
        <div className="ue-h"><b className="mono">{u.id}</b><span className="mono" style={{ color: c }}>{u.last?.serving_cell ?? '—'}</span></div>
        <Sparkline points={u.sinr} width={150} height={34} color={c} yMin={-10} yMax={40} />
        <ServingStrip strip={u.serving} color={color} height={5} />
        <div className="ue-f"><span className={`dot ${q}`} />SINR {u.last ? u.last.sinr_db.toFixed(1) : '—'} dB<span className="muted">MCS {u.last?.mcs_dl ?? '—'} · {u.last ? u.last.throughput_dl_mbps.toFixed(1) : '—'} Mb/s</span></div>
      </button>); })}</div>
  );
}
