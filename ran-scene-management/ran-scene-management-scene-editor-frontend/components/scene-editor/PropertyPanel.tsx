'use client';
import { useEffect, useState } from 'react';
import type { Selection } from '@/hooks/feature/useSceneEditorPage';
import type { AntennaPreset, Cell, Gnb } from '@/types/registry';

interface Props {
  selection: Selection; presets: AntennaPreset[]; saving: boolean; message: string | null;
  onCell: (c: Cell, f: Partial<Cell>) => void; onGnb: (g: Gnb, f: Partial<Gnb>) => void; onAntenna: (c: Cell, uuid: string | null) => void;
}

/** 選中物件的屬性表單。呈現與表單狀態;寫回交給 hook。 */
export function PropertyPanel({ selection, presets, saving, message, onCell, onGnb, onAntenna }: Props) {
  const [form, setForm] = useState<Record<string, string>>({});
  useEffect(() => {
    if (selection?.kind === 'cell') { const c = selection.cell; setForm({ pci: String(c.pci), center_frequency_ghz: String(c.center_frequency_ghz ?? ''), bandwidth_mhz: String(c.bandwidth_mhz), power_dbm: String(c.power_dbm), azimuth_deg: String(c.azimuth_deg), tilt_deg: String(c.tilt_deg) }); }
    else if (selection?.kind === 'gnb') { const g = selection.gnb; setForm({ name: g.name, gnb_id: String(g.gnb_id), plmn_mcc: g.plmn_mcc, plmn_mnc: g.plmn_mnc, x: String(g.position[0] ?? 0), y: String(g.position[1] ?? 0), z: String(g.position[2] ?? 0) }); }
    else setForm({});
  }, [selection]);
  const f = (k: string) => form[k] ?? '';
  const num = (k: string) => (form[k] === '' ? null : Number(form[k]));
  if (!selection) return <aside className="panel"><p className="muted">點選畫布或物件樹裡的東西</p></aside>;
  if (selection.kind === 'cell') {
    const c = selection.cell;
    return (
      <aside className="panel">
        <h3>Cell · {c.name}</h3>
        <p className="muted">{selection.gnb.name}{c.position ? ' · 獨立位置(DAS)' : ' · 共站'}</p>
        {(['pci', 'center_frequency_ghz', 'bandwidth_mhz', 'power_dbm', 'azimuth_deg', 'tilt_deg'] as const).map((k) => (
          <label key={k}><span>{k}</span><input value={f(k)} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></label>
        ))}
        <label><span>天線 preset</span>
          <select value={c.ru?.f_antenna_preset_uuid ?? ''} onChange={(e) => onAntenna(c, e.target.value || null)}>
            <option value="">(未指定)</option>
            {presets.map((p) => <option key={p.antenna_preset_uuid} value={p.antenna_preset_uuid}>{p.name} — {p.pattern} {p.rows}×{p.cols} {p.polarization}</option>)}
          </select>
        </label>
        <div className="actions">
          <button disabled={saving} onClick={() => onCell(c, { pci: Number(f('pci')), center_frequency_ghz: num('center_frequency_ghz'), bandwidth_mhz: Number(f('bandwidth_mhz')), power_dbm: Number(f('power_dbm')), azimuth_deg: Number(f('azimuth_deg')), tilt_deg: Number(f('tilt_deg')) })}>儲存</button>
          <button disabled={saving} onClick={() => onCell(c, { is_active: !c.is_active })}>{c.is_active ? '關閉 cell' : '開啟 cell'}</button>
        </div>
        {message && <p className="msg">{message}</p>}
      </aside>
    );
  }
  if (selection.kind === 'gnb') {
    const g = selection.gnb;
    return (
      <aside className="panel">
        <h3>gNB · {g.name}</h3>
        {(['name', 'gnb_id', 'plmn_mcc', 'plmn_mnc', 'x', 'y', 'z'] as const).map((k) => (
          <label key={k}><span>{k}</span><input value={f(k)} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></label>
        ))}
        <div className="actions">
          <button disabled={saving} onClick={() => onGnb(g, { name: f('name'), gnb_id: Number(f('gnb_id')), plmn_mcc: f('plmn_mcc'), plmn_mnc: f('plmn_mnc'), position: [Number(f('x')), Number(f('y')), Number(f('z'))] })}>儲存</button>
        </div>
        {message && <p className="msg">{message}</p>}
      </aside>
    );
  }
  if (selection.kind === 'ue') {
    const u = selection.ue;
    return (
      <aside className="panel"><h3>UE · {u.name}</h3>
        <p>天線高 {u.antenna_height_m} m · 5QI {u.qos_5qi} · {u.waypoints.length} waypoints</p>
        <p className="muted">在場時段 {u.active_windows.length ? u.active_windows.map((w) => `${w[0]}–${w[1]}s`).join(', ') : '全程'}</p>
        <p className="muted">流量 {u.traffic.map((t) => `${t.pattern}${t.schedule ? ` ${t.schedule.length} 段` : ''}`).join(', ') || '—'}</p>
        <p className="muted">UE 軌跡/流量編輯:P3-2</p>
      </aside>
    );
  }
  return <aside className="panel"><h3>建築 #{selection.index + 1}</h3><p className="muted">材質選單:P3-2</p></aside>;
}
