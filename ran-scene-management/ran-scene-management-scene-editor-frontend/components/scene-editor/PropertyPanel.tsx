'use client';
import { useEffect, useState } from 'react';
import type { Selection } from '@/hooks/feature/useSceneEditorPage';
import { RUN_KNOB_KEYS } from '@/config';
import type { AntennaPreset, Building, Cell, Du, DuConfigTemplate, Gnb, Material, RunKnob, SceneRun, Ue } from '@/types/registry';

type Tab = 'props' | 'antenna' | 'ran';
interface Props {
  selection: Selection; presets: AntennaPreset[]; templates: DuConfigTemplate[]; materials: Material[]; run: SceneRun | null; knobs: RunKnob[]; saving: boolean; message: string | null;
  onCell: (c: Cell, f: Partial<Cell>) => void; onGnb: (g: Gnb, f: Partial<Gnb>) => void; onDu: (d: Du, f: Partial<Du>) => void; onUe: (u: Ue, f: Partial<Ue>) => void; onBuilding: (b: Building, f: Partial<Building>) => void;
  onCellAntenna: (c: Cell, uuid: string | null) => void; onUeAntenna: (u: Ue, uuid: string | null) => void; onRun: (f: Partial<SceneRun>) => void; onKnob: (k: string, v: string) => void; onRemoveKnob: (uuid: string) => void; onDelete: () => void;
}
const Field = ({ k, label, v, set, type = 'text' }: { k: string; label?: string; v: string; set: (k: string, v: string) => void; type?: string }) => <label><span>{label ?? k}</span><input type={type} value={v} onChange={(e) => set(k, e.target.value)} /></label>;

/** 右側面板:屬性 / 天線 / RAN 參數 三個分頁;表單狀態在此,寫回交給 hook */
export function PropertyPanel(p: Props) {
  const { selection: sel } = p;
  const [tab, setTab] = useState<Tab>('props'); const [form, setForm] = useState<Record<string, string>>({}); const [knobKey, setKnobKey] = useState<string>(RUN_KNOB_KEYS[0]); const [knobVal, setKnobVal] = useState('');
  useEffect(() => {
    if (sel?.kind === 'cell') { const c = sel.cell; setForm({ name: c.name, pci: String(c.pci), center_frequency_ghz: String(c.center_frequency_ghz ?? ''), bandwidth_mhz: String(c.bandwidth_mhz), power_dbm: String(c.power_dbm), azimuth_deg: String(c.azimuth_deg), tilt_deg: String(c.tilt_deg), band: c.band, override: JSON.stringify(c.ru?.antenna_override ?? {}, null, 1), du_override: JSON.stringify(sel.gnb.dus[0]?.config_override ?? {}, null, 1) }); }
    else if (sel?.kind === 'gnb') { const g = sel.gnb; setForm({ name: g.name, gnb_id: String(g.gnb_id), plmn_mcc: g.plmn_mcc, plmn_mnc: g.plmn_mnc, x: String(g.position[0] ?? 0), y: String(g.position[1] ?? 0), z: String(g.position[2] ?? 0), a3_offset_db: String(g.a3_offset_db ?? ''), a3_hys_db: String(g.a3_hys_db ?? ''), a3_ttt_ms: String(g.a3_ttt_ms ?? ''), du_override: JSON.stringify(g.dus[0]?.config_override ?? {}, null, 1) }); }
    else if (sel?.kind === 'ue') { const u = sel.ue; setForm({ name: u.name, antenna_height_m: String(u.antenna_height_m), qos_5qi: String(u.qos_5qi), speed_mps: String(u.speed_mps ?? '') }); }
    else if (sel?.kind === 'building') { const b = sel.building; setForm({ name: b.name, x: String(b.position[0] ?? 0), z: String(b.position[2] ?? 0), sx: String(b.size[0] ?? 10), sy: String(b.size[1] ?? 6), sz: String(b.size[2] ?? 10) }); }
    else setForm({});
  }, [sel]);
  const f = (k: string) => form[k] ?? ''; const set = (k: string, v: string) => setForm((o) => ({ ...o, [k]: v })); const num = (k: string) => (form[k] === '' ? null : Number(form[k]));
  const parse = (s: string) => { try { return JSON.parse(s); } catch { return undefined; } };
  const head = sel ? { gnb: `gNB · ${sel.kind === 'gnb' ? sel.gnb.name : ''}`, cell: `Cell · ${sel.kind === 'cell' ? sel.cell.name : ''}`, ue: `UE · ${sel.kind === 'ue' ? sel.ue.name : ''}`, building: `建築 · ${sel.kind === 'building' ? sel.building.name : ''}` }[sel.kind] : '場景 / Run';
  const tabs: { k: Tab; l: string }[] = [{ k: 'props', l: '屬性' }, { k: 'antenna', l: '天線' }, { k: 'ran', l: 'RAN 參數' }];
  return (
    <aside className="panel">
      <div className="panel-head"><h3>{head}</h3>{sel && <button className="ghost danger" disabled={p.saving} onClick={() => { if (confirm('刪除這個物件?')) p.onDelete(); }}>刪除</button>}</div>
      <div className="tabs">{tabs.map((t) => <button key={t.k} className={tab === t.k ? 'on' : ''} onClick={() => setTab(t.k)}>{t.l}</button>)}</div>
      {tab === 'props' && (!sel ? <p className="muted">點畫布或物件樹選一個物件;或在這裡改 run 的模式/倍速。</p>
        : sel.kind === 'cell' ? <>
          <p className="muted small">{sel.gnb.name}{sel.cell.position ? ' · 獨立位置(DAS)' : ' · 共站'}</p>
          <Field k="name" v={f('name')} set={set} /><Field k="pci" v={f('pci')} set={set} type="number" /><Field k="band" v={f('band')} set={set} /><Field k="center_frequency_ghz" label="中心頻率 GHz" v={f('center_frequency_ghz')} set={set} type="number" /><Field k="bandwidth_mhz" label="頻寬 MHz" v={f('bandwidth_mhz')} set={set} type="number" /><Field k="power_dbm" label="功率 dBm" v={f('power_dbm')} set={set} type="number" /><Field k="azimuth_deg" label="方位角 °" v={f('azimuth_deg')} set={set} type="number" /><Field k="tilt_deg" label="下傾 °" v={f('tilt_deg')} set={set} type="number" />
          <div className="actions"><button className="primary" disabled={p.saving} onClick={() => p.onCell(sel.cell, { name: f('name'), pci: Number(f('pci')), band: f('band'), center_frequency_ghz: num('center_frequency_ghz'), bandwidth_mhz: Number(f('bandwidth_mhz')), power_dbm: Number(f('power_dbm')), azimuth_deg: Number(f('azimuth_deg')), tilt_deg: Number(f('tilt_deg')) })}>儲存</button>
            <button disabled={p.saving} onClick={() => p.onCell(sel.cell, { is_active: !sel.cell.is_active })}>{sel.cell.is_active ? '關閉 cell' : '開啟 cell'}</button></div></>
        : sel.kind === 'gnb' ? <>
          <Field k="name" v={f('name')} set={set} /><Field k="gnb_id" v={f('gnb_id')} set={set} type="number" /><Field k="plmn_mcc" label="MCC" v={f('plmn_mcc')} set={set} /><Field k="plmn_mnc" label="MNC" v={f('plmn_mnc')} set={set} />
          <div className="xyz"><Field k="x" v={f('x')} set={set} type="number" /><Field k="y" v={f('y')} set={set} type="number" /><Field k="z" v={f('z')} set={set} type="number" /></div>
          <div className="actions"><button className="primary" disabled={p.saving} onClick={() => p.onGnb(sel.gnb, { name: f('name'), gnb_id: Number(f('gnb_id')), plmn_mcc: f('plmn_mcc'), plmn_mnc: f('plmn_mnc'), position: [Number(f('x')), Number(f('y')), Number(f('z'))] })}>儲存</button>
            <button disabled={p.saving} onClick={() => p.onGnb(sel.gnb, { is_active: !sel.gnb.is_active })}>{sel.gnb.is_active ? '停用 gNB' : '啟用 gNB'}</button></div></>
        : sel.kind === 'ue' ? <>
          <Field k="name" v={f('name')} set={set} /><Field k="antenna_height_m" label="天線高 m" v={f('antenna_height_m')} set={set} type="number" /><Field k="qos_5qi" label="5QI" v={f('qos_5qi')} set={set} type="number" /><Field k="speed_mps" label="速度 m/s" v={f('speed_mps')} set={set} type="number" />
          <p className="muted small">{sel.ue.waypoints.length} waypoints · 在場 {sel.ue.active_windows.length ? sel.ue.active_windows.map((w) => `${w[0]}–${w[1]}s`).join(', ') : '全程'} · 流量 {sel.ue.traffic.map((t) => t.pattern).join(', ') || '—'}</p>
          <div className="actions"><button className="primary" disabled={p.saving} onClick={() => p.onUe(sel.ue, { name: f('name'), antenna_height_m: Number(f('antenna_height_m')), qos_5qi: Number(f('qos_5qi')), speed_mps: num('speed_mps') })}>儲存</button></div></>
        : <>
          <Field k="name" v={f('name')} set={set} /><div className="xyz"><Field k="x" v={f('x')} set={set} type="number" /><Field k="z" v={f('z')} set={set} type="number" /></div>
          <div className="xyz"><Field k="sx" label="寬" v={f('sx')} set={set} type="number" /><Field k="sy" label="高" v={f('sy')} set={set} type="number" /><Field k="sz" label="深" v={f('sz')} set={set} type="number" /></div>
          <label><span>材質</span><select value={sel.building.f_material_uuid ?? ''} onChange={(e) => p.onBuilding(sel.building, { f_material_uuid: e.target.value || null })}><option value="">(場景預設)</option>{p.materials.map((m) => <option key={m.material_uuid} value={m.material_uuid}>{m.key} · ITU {m.itu_id}</option>)}</select></label>
          <p className="muted small">來源 {sel.building.source}{sel.building.geometry_ref ? ` · ${sel.building.geometry_ref.split('/').pop()}` : ''}</p>
          <div className="actions"><button className="primary" disabled={p.saving} onClick={() => p.onBuilding(sel.building, { name: f('name'), position: [Number(f('x')), 0, Number(f('z'))], size: [Number(f('sx')), Number(f('sy')), Number(f('sz'))] })}>儲存</button></div></>)}
      {tab === 'antenna' && (sel?.kind === 'cell' ? <>
          <label><span>陣列 preset</span><select value={sel.cell.ru?.f_antenna_preset_uuid ?? ''} onChange={(e) => p.onCellAntenna(sel.cell, e.target.value || null)}><option value="">(未指定 → 1×1 iso)</option>{p.presets.map((a) => <option key={a.antenna_preset_uuid} value={a.antenna_preset_uuid}>{a.name} — {a.pattern} {a.rows}×{a.cols} {a.polarization}</option>)}</select></label>
          {sel.cell.ru?.antenna_preset && <dl className="kv"><dt>pattern</dt><dd>{sel.cell.ru.antenna_preset.pattern}</dd><dt>陣列</dt><dd>{sel.cell.ru.antenna_preset.rows}×{sel.cell.ru.antenna_preset.cols} · {sel.cell.ru.antenna_preset.polarization}</dd><dt>間距 λ</dt><dd>{sel.cell.ru.antenna_preset.v_spacing} / {sel.cell.ru.antenna_preset.h_spacing}</dd><dt>max gain</dt><dd>{sel.cell.ru.antenna_preset.max_gain_dbi} dBi</dd></dl>}
          <label><span>RU 覆寫 JSON</span><textarea rows={4} value={f('override')} onChange={(e) => set('override', e.target.value)} /></label>
          <div className="actions"><button className="primary" disabled={p.saving || parse(f('override')) === undefined} onClick={() => p.onCellAntenna(sel.cell, sel.cell.ru?.f_antenna_preset_uuid ?? null)}>套用</button></div>
          <p className="muted small">噪聲係數 {sel.cell.ru?.noise_figure_db ?? '—'} dB · 陣列種類在「網路元件」頁維護</p></>
        : sel?.kind === 'ue' ? <label><span>UE 天線</span><select value={sel.ue.f_antenna_preset_uuid ?? ''} onChange={(e) => p.onUeAntenna(sel.ue, e.target.value || null)}><option value="">(預設 1×1)</option>{p.presets.map((a) => <option key={a.antenna_preset_uuid} value={a.antenna_preset_uuid}>{a.name} — {a.rows}×{a.cols}</option>)}</select></label>
        : <p className="muted">選一個 cell 或 UE 設定天線陣列。</p>)}
      {tab === 'ran' && <>
        {(sel?.kind === 'gnb' || sel?.kind === 'cell') && (() => { const g = sel.kind === 'gnb' ? sel.gnb : sel.gnb; const du = g.dus[0]; return <>
          <div className="row head">DU 設定模板 <span className="muted">{du?.name}</span></div>
          <label><span>模板</span><select value={du?.f_du_config_template_uuid ?? ''} onChange={(e) => du && p.onDu(du, { f_du_config_template_uuid: e.target.value || null })}><option value="">(服務預設)</option>{p.templates.map((t) => <option key={t.du_config_template_uuid} value={t.du_config_template_uuid}>{t.name} — {t.tdd_pattern} μ{t.numerology} {t.n_prb} PRB</option>)}</select></label>
          {du?.config_template && <dl className="kv"><dt>PF α</dt><dd>{du.config_template.pf_alpha}</dd><dt>BLER 目標</dt><dd>{du.config_template.target_bler}</dd><dt>discard</dt><dd>{du.config_template.rlc_discard_timer_ms} ms</dd><dt>HARQ</dt><dd>{du.config_template.harq_max_retx} retx</dd></dl>}
          <label><span>DU 覆寫 JSON</span><textarea rows={4} value={f('du_override')} onChange={(e) => set('du_override', e.target.value)} /></label>
          <div className="actions"><button className="primary" disabled={p.saving || parse(f('du_override')) === undefined} onClick={() => du && p.onDu(du, { config_override: parse(f('du_override')) })}>套用覆寫</button></div>
          <div className="row head">A3 換手(gNB)</div>
          <div className="xyz"><Field k="a3_offset_db" label="offset dB" v={f('a3_offset_db')} set={set} type="number" /><Field k="a3_hys_db" label="hys dB" v={f('a3_hys_db')} set={set} type="number" /><Field k="a3_ttt_ms" label="TTT ms" v={f('a3_ttt_ms')} set={set} type="number" /></div>
          <div className="actions"><button className="primary" disabled={p.saving} onClick={() => p.onGnb(g, { a3_enabled: true, a3_offset_db: num('a3_offset_db'), a3_hys_db: num('a3_hys_db'), a3_ttt_ms: num('a3_ttt_ms') })}>儲存 A3</button><button disabled={p.saving} onClick={() => p.onGnb(g, { a3_enabled: false })}>停用 A3</button></div></>; })()}
        <div className="row head">Run 設定 <span className="muted">{p.run ? p.run.status : '尚無 run(儲存即建 draft)'}</span></div>
        <label><span>模式</span><select value={p.run?.mode ?? 'live'} onChange={(e) => p.onRun({ mode: e.target.value as SceneRun['mode'] })}><option value="live">live(Sionna 即時)</option><option value="cached">cached(預算 npz)</option></select></label>
        <label><span>倍速</span><input type="number" defaultValue={p.run?.speed_x ?? 1} onBlur={(e) => Number(e.target.value) !== (p.run?.speed_x ?? 1) && p.onRun({ speed_x: Number(e.target.value) })} /></label>
        <label><span>sim_dt ms</span><input type="number" defaultValue={p.run?.sim_dt_ms ?? 500} onBlur={(e) => Number(e.target.value) !== (p.run?.sim_dt_ms ?? 500) && p.onRun({ sim_dt_ms: Number(e.target.value) })} /></label>
        <label><span>時長 s</span><input type="number" defaultValue={p.run?.duration_sec ?? 3600} onBlur={(e) => Number(e.target.value) !== (p.run?.duration_sec ?? 3600) && p.onRun({ duration_sec: Number(e.target.value) })} /></label>
        <div className="row head">Run knobs <span className="muted">inter_freq / cell_quotas / tx_power…</span></div>
        <ul className="knobs">{p.knobs.map((k) => <li key={k.run_knob_uuid}><b className="mono">{k.key}</b><span className="mono small">{typeof k.value === 'string' ? k.value : JSON.stringify(k.value)}</span><button className="ghost" onClick={() => p.onRemoveKnob(k.run_knob_uuid)}>×</button></li>)}</ul>
        <form className="inline" onSubmit={(e) => { e.preventDefault(); if (knobVal.trim()) { p.onKnob(knobKey, knobVal.trim()); setKnobVal(''); } }}><select value={knobKey} onChange={(e) => setKnobKey(e.target.value)}>{RUN_KNOB_KEYS.map((k) => <option key={k}>{k}</option>)}</select><input placeholder="值(JSON 或字串)" value={knobVal} onChange={(e) => setKnobVal(e.target.value)} /><button type="submit" disabled={p.saving}>設定</button></form>
      </>}
      {p.message && <p className="msg">{p.message}</p>}
    </aside>
  );
}
