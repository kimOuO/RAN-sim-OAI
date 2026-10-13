'use client';
import { useEffect, useState, type ReactNode } from 'react';
import { DuFields } from '@/components/scene-editor/DuFields';
import type { Selection } from '@/hooks/feature/useSceneEditorPage';
import { ANTENNA_PATTERNS, POLARIZATIONS, RUN_KNOB_KEYS, CATEGORY_OPTIONS, categoryOfScene } from '@/config';
import type { AntennaPreset, Building, Cell, Du, DuConfigTemplate, Gnb, GnbConfigTemplate, Material, RunKnob, SceneRun, SceneTree, Ue } from '@/types/registry';

export type Tab = 'props' | 'antenna' | 'ran';
interface Props {
  selection: Selection; presets: AntennaPreset[]; templates: DuConfigTemplate[]; gnbTemplates: GnbConfigTemplate[]; materials: Material[]; run: SceneRun | null; knobs: RunKnob[]; saving: boolean; message: string | null;
  scene: SceneTree['scene']; onSceneAntenna: (which: 'gnb' | 'ue', uuid: string | null) => void;
  onE2Block?: (block: number | null) => void;
  gnbs?: Gnb[];
  onCategory?: (category: string | null) => void;   // 場景分類(資料化;null = 退回名字前綴規則)
  onApplyGnbTemplate: (g: Gnb, t: GnbConfigTemplate) => void; onSaveGnbTemplate: (g: Gnb, name: string, uuid: string | null) => void;
  onAntennaFields: (c: Cell, f: Partial<AntennaPreset>) => void; onSaveAntennaPreset: (c: Cell, f: Partial<AntennaPreset>, name: string, uuid: string | null) => void;
  onCell: (c: Cell, f: Partial<Cell>) => void; onGnb: (g: Gnb, f: Partial<Gnb>) => void; onDu: (d: Du, f: Partial<Du>) => void; onUe: (u: Ue, f: Partial<Ue>) => void; onBuilding: (b: Building, f: Partial<Building>) => void;
  /** 這一步要顯示的分頁(預設三個全開);showRun = RAN 分頁要不要帶 run 設定;extra = 選到 UE 時附加在屬性分頁下方 */
  tabs?: Tab[]; showRun?: boolean; extra?: ReactNode; emptyHint?: string;
  onCellAntenna: (c: Cell, uuid: string | null) => void; onUeAntenna: (u: Ue, uuid: string | null) => void; onRun: (f: Partial<SceneRun>) => void; onKnob: (k: string, v: string) => void; onRemoveKnob: (uuid: string) => void; onDelete: () => void;
}
/** 天線分頁的表單初值:RU 覆寫 > preset > 1×1 iso */
const antennaForm = (c: Cell): Record<string, string> => { const o = (c.ru?.antenna_override ?? {}) as Partial<AntennaPreset>; const a = c.ru?.antenna_preset; const g = <K extends keyof AntennaPreset>(k: K, d: AntennaPreset[K]) => String(o[k] ?? a?.[k] ?? d); return { an_pattern: g('pattern', 'iso'), an_rows: g('rows', 1), an_cols: g('cols', 1), an_polarization: g('polarization', 'V'), an_v_spacing: g('v_spacing', 0.5), an_h_spacing: g('h_spacing', 0.5), an_max_gain_dbi: g('max_gain_dbi', 0), an_polarization_model: g('polarization_model', 'tr38901_2') }; };
const Field = ({ k, label, v, set, type = 'text', readOnly, title }: { k: string; label?: string; v: string; set: (k: string, v: string) => void; type?: string; readOnly?: boolean; title?: string }) => <label title={title}><span>{label ?? k}</span><input type={type} value={v} readOnly={readOnly} disabled={readOnly} onChange={(e) => set(k, e.target.value)} /></label>;

/** 右側面板:屬性 / 天線 / RAN 參數 三個分頁;表單狀態在此,寫回交給 hook */
const catLabel = (k: string) => CATEGORY_OPTIONS.find((c) => c.key === k)?.label ?? '其他';

export function PropertyPanel(p: Props) {
  const { selection: sel } = p;
  const allowed = p.tabs ?? ['props', 'antenna', 'ran'];
  const [tab, setTab] = useState<Tab>(allowed[0]); const [form, setForm] = useState<Record<string, string>>({}); const [knobKey, setKnobKey] = useState<string>(RUN_KNOB_KEYS[0]); const [knobVal, setKnobVal] = useState('');
  useEffect(() => {
    if (sel?.kind === 'cell') { const c = sel.cell; setForm({ name: c.name, pci: String(c.pci), center_frequency_ghz: String(c.center_frequency_ghz ?? ''), bandwidth_mhz: String(c.bandwidth_mhz), power_dbm: String(c.power_dbm), azimuth_deg: String(c.azimuth_deg), tilt_deg: String(c.tilt_deg), band: c.band, override: JSON.stringify(c.ru?.antenna_override ?? {}, null, 1), ...antennaForm(c), du_override: JSON.stringify(sel.gnb.dus[0]?.config_override ?? {}, null, 1) }); }
    else if (sel?.kind === 'gnb') { const g = sel.gnb; setForm({ name: g.name, gnb_id: String(g.gnb_id), plmn_mcc: g.plmn_mcc, plmn_mnc: g.plmn_mnc, x: String(g.position[0] ?? 0), y: String(g.position[1] ?? 0), z: String(g.position[2] ?? 0), a3_offset_db: String(g.a3_offset_db ?? ''), a3_hys_db: String(g.a3_hys_db ?? ''), a3_ttt_ms: String(g.a3_ttt_ms ?? ''), du_override: JSON.stringify(g.dus[0]?.config_override ?? {}, null, 1) }); }
    else if (sel?.kind === 'ue') { const u = sel.ue; setForm({ name: u.name, antenna_height_m: String(u.antenna_height_m), qos_5qi: String(u.qos_5qi), speed_mps: String(u.speed_mps ?? '') }); }
    else if (sel?.kind === 'building') { const b = sel.building; setForm({ name: b.name, x: String(b.position[0] ?? 0), z: String(b.position[2] ?? 0), sx: String(b.size[0] ?? 10), sy: String(b.size[1] ?? 6), sz: String(b.size[2] ?? 10) }); }
    else setForm({});
  }, [sel]);
  const f = (k: string) => form[k] ?? ''; const set = (k: string, v: string) => setForm((o) => ({ ...o, [k]: v })); const num = (k: string) => (form[k] === '' ? null : Number(form[k]));
  const parse = (s: string) => { try { return JSON.parse(s); } catch { return undefined; } };
  const head = sel ? { gnb: `gNB · ${sel.kind === 'gnb' ? sel.gnb.name : ''}`, cell: `Cell · ${sel.kind === 'cell' ? sel.cell.name : ''}`, ue: `UE · ${sel.kind === 'ue' ? sel.ue.name : ''}`, building: `建築 · ${sel.kind === 'building' ? sel.building.name : ''}` }[sel.kind] : '場景 / Run';
  const tabs: { k: Tab; l: string }[] = ([{ k: 'props', l: '屬性' }, { k: 'antenna', l: '天線' }, { k: 'ran', l: 'RAN 參數' }] as { k: Tab; l: string }[]).filter((t) => allowed.includes(t.k));
  return (
    <aside className="panel">
      <div className="panel-head"><h3>{head}</h3>{sel && <button className="ghost danger" disabled={p.saving} onClick={() => { if (confirm('刪除這個物件?')) p.onDelete(); }}>刪除</button>}</div>
      {tabs.length > 1 && <div className="tabs">{tabs.map((t) => <button key={t.k} className={tab === t.k ? 'on' : ''} onClick={() => setTab(t.k)}>{t.l}</button>)}</div>}
      {tab === 'props' && (!sel ? <p className="muted">{p.emptyHint ?? '點畫布或物件樹選一個物件。'}</p>
        : sel.kind === 'cell' ? <>
          <p className="muted small">{sel.gnb.name}{sel.cell.position ? ' · 獨立位置(DAS)' : ' · 共站'}</p>
          <Field k="name" v={f('name')} set={set} /><Field k="pci" v={f('pci')} set={set} type="number" /><Field k="band" v={f('band')} set={set} /><Field k="center_frequency_ghz" label="中心頻率 GHz" v={f('center_frequency_ghz')} set={set} type="number" /><Field k="bandwidth_mhz" label="頻寬 MHz" v={f('bandwidth_mhz')} set={set} type="number" /><Field k="power_dbm" label="功率 dBm" v={f('power_dbm')} set={set} type="number" /><Field k="azimuth_deg" label="方位角 °" v={f('azimuth_deg')} set={set} type="number" /><Field k="tilt_deg" label="下傾 °" v={f('tilt_deg')} set={set} type="number" />
          <div className="actions"><button className="primary" disabled={p.saving} onClick={() => p.onCell(sel.cell, { name: f('name'), pci: Number(f('pci')), band: f('band'), center_frequency_ghz: num('center_frequency_ghz'), bandwidth_mhz: Number(f('bandwidth_mhz')), power_dbm: Number(f('power_dbm')), azimuth_deg: Number(f('azimuth_deg')), tilt_deg: Number(f('tilt_deg')) })}>儲存</button>
            <button disabled={p.saving} onClick={() => p.onCell(sel.cell, { is_active: !sel.cell.is_active })}>{sel.cell.is_active ? '關閉 cell' : '開啟 cell'}</button></div></>
        : sel.kind === 'gnb' ? <>
          <div className="tpl-row"><span className="row head">gNB 模板</span>
            <select value={sel.gnb.f_gnb_config_template_uuid ?? ''} onChange={(e) => { const t = p.gnbTemplates.find((x) => x.gnb_config_template_uuid === e.target.value); if (t && confirm(`套用「${t.name}」到 ${sel.gnb.name}?會覆蓋 PLMN / A3 / DU 模板 / 每個 cell 的 RF 與天線,之後仍可現場改。`)) p.onApplyGnbTemplate(sel.gnb, t); }}><option value="">(選一個模板快速填值)</option>{p.gnbTemplates.map((t) => <option key={t.gnb_config_template_uuid} value={t.gnb_config_template_uuid}>{t.name}{t.source === 'oai' ? ' · OAI' : ''}</option>)}</select>
            <div className="actions"><button disabled={p.saving} onClick={() => { const n = prompt('新模板名稱', `${sel.gnb.name}-模板`); if (n) p.onSaveGnbTemplate(sel.gnb, n, null); }}>現場存成新模板</button>{sel.gnb.config_template && <button disabled={p.saving} onClick={() => { if (confirm(`用 ${sel.gnb.name} 的現場值更新模板「${sel.gnb.config_template!.name}」?`)) p.onSaveGnbTemplate(sel.gnb, sel.gnb.config_template!.name, sel.gnb.config_template!.gnb_config_template_uuid); }}>更新模板「{sel.gnb.config_template.name}」</button>}</div>
            {sel.gnb.config_template && <p className="muted small">來源模板 {sel.gnb.config_template.name};現場改值不會自動回寫。</p>}</div>
          <Field k="name" v={f('name')} set={set} /><Field k="gnb_id" v={f('gnb_id')} set={set} type="number" /><Field k="plmn_mcc" label="MCC" v={f('plmn_mcc')} set={set} /><Field k="plmn_mnc" label="MNC" v={f('plmn_mnc')} set={set} />
          <div className="xyz"><Field k="x" v={f('x')} set={set} type="number" /><Field k="y" v={f('y')} set={set} type="number" /><Field k="z" v={f('z')} set={set} type="number" /></div>
          <div className="actions"><button className="primary" disabled={p.saving} onClick={() => p.onGnb(sel.gnb, { name: f('name'), gnb_id: Number(f('gnb_id')), plmn_mcc: f('plmn_mcc'), plmn_mnc: f('plmn_mnc'), position: [Number(f('x')), Number(f('y')), Number(f('z'))] })}>儲存</button>
            <button disabled={p.saving} onClick={() => p.onGnb(sel.gnb, { is_active: !sel.gnb.is_active })}>{sel.gnb.is_active ? '停用 gNB' : '啟用 gNB'}</button></div></>
        : sel.kind === 'ue' ? <>
          <Field k="name" v={f('name')} set={set} /><Field k="antenna_height_m" label="天線高 m" v={f('antenna_height_m')} set={set} type="number" /><Field k="qos_5qi" label="5QI" v={f('qos_5qi')} set={set} type="number" /><Field k="speed_mps" label="速度 m/s" v={f('speed_mps')} set={set} type="number" />
          <p className="muted small">{sel.ue.waypoints.length} waypoints · 在場 {sel.ue.active_windows.length ? sel.ue.active_windows.map((w) => `${w[0]}–${w[1]}s`).join(', ') : '全程'} · 流量 {sel.ue.traffic.map((t) => t.pattern).join(', ') || '—'}</p>
          <div className="actions"><button className="primary" disabled={p.saving} onClick={() => p.onUe(sel.ue, { name: f('name'), antenna_height_m: Number(f('antenna_height_m')), qos_5qi: Number(f('qos_5qi')), speed_mps: num('speed_mps') })}>儲存</button></div>{p.extra}</>
        : <>
          <Field k="name" v={f('name')} set={set} /><div className="xyz"><Field k="x" v={f('x')} set={set} type="number" /><Field k="z" v={f('z')} set={set} type="number" /></div>
          <div className="xyz"><Field k="sx" label="寬" v={f('sx')} set={set} type="number" /><Field k="sy" label="高" v={f('sy')} set={set} type="number" /><Field k="sz" label="深" v={f('sz')} set={set} type="number" /></div>
          <label><span>材質</span><select value={sel.building.f_material_uuid ?? ''} onChange={(e) => p.onBuilding(sel.building, { f_material_uuid: e.target.value || null })}><option value="">(場景預設)</option>{p.materials.map((m) => <option key={m.material_uuid} value={m.material_uuid}>{m.key} · ITU {m.itu_id}</option>)}</select></label>
          <p className="muted small">來源 {sel.building.source}{sel.building.geometry_ref ? ` · ${sel.building.geometry_ref.split('/').pop()}` : ''}</p>
          <div className="actions"><button className="primary" disabled={p.saving} onClick={() => p.onBuilding(sel.building, { name: f('name'), position: [Number(f('x')), 0, Number(f('z'))], size: [Number(f('sx')), Number(f('sy')), Number(f('sz'))] })}>儲存</button></div></>)}
      {tab === 'antenna' && (sel?.kind === 'cell' ? <>
          <label><span>陣列 preset</span><select value={sel.cell.ru?.f_antenna_preset_uuid ?? ''} onChange={(e) => p.onCellAntenna(sel.cell, e.target.value || null)}><option value="">(未指定 → 1×1 tr38901)</option>{p.presets.map((a) => <option key={a.antenna_preset_uuid} value={a.antenna_preset_uuid}>{a.name} — {a.pattern} {a.rows}×{a.cols} {a.polarization}</option>)}</select></label>
          <div className="row head">現場調整 <span className="muted">{sel.cell.ru?.antenna_override && Object.keys(sel.cell.ru.antenna_override as object).length ? '此 RU 有覆寫' : '沿用 preset'}</span></div>
          <label><span>pattern</span><select value={f('an_pattern')} onChange={(e) => set('an_pattern', e.target.value)}>{ANTENNA_PATTERNS.map((x) => <option key={x}>{x}</option>)}</select></label>
          <div className="xyz"><Field k="an_rows" label="rows" v={f('an_rows')} set={set} type="number" /><Field k="an_cols" label="cols" v={f('an_cols')} set={set} type="number" /><label><span>極化</span><select value={f('an_polarization')} onChange={(e) => set('an_polarization', e.target.value)}>{POLARIZATIONS.map((x) => <option key={x}>{x}</option>)}</select></label></div>
          <div className="xyz"><Field k="an_v_spacing" label="v λ" v={f('an_v_spacing')} set={set} type="number" /><Field k="an_h_spacing" label="h λ" v={f('an_h_spacing')} set={set} type="number" /><Field k="an_max_gain_dbi" label="max dBi" v={f('an_max_gain_dbi')} set={set} type="number" readOnly title="僅供辨識,不影響模擬:tr38901 的 8 dBi 元件增益已包含在 Sionna 的輻射圖裡,再讀一次會重複計算" /></div>
          {(() => { const fields = (): Partial<AntennaPreset> => ({ pattern: f('an_pattern') as AntennaPreset['pattern'], rows: Number(f('an_rows')), cols: Number(f('an_cols')), polarization: f('an_polarization') as AntennaPreset['polarization'], v_spacing: Number(f('an_v_spacing')), h_spacing: Number(f('an_h_spacing')), max_gain_dbi: Number(f('an_max_gain_dbi')), polarization_model: f('an_polarization_model') }); const cur = sel.cell.ru?.antenna_preset; return (
            <div className="actions"><button className="primary" disabled={p.saving} onClick={() => p.onAntennaFields(sel.cell, fields())}>套用到此 RU(覆寫)</button>
              <button disabled={p.saving} onClick={() => { const n = prompt('新天線 preset 名稱', `${f('an_pattern')} ${f('an_rows')}×${f('an_cols')} ${f('an_polarization')}`); if (n) p.onSaveAntennaPreset(sel.cell, fields(), n, null); }}>存成新 preset</button>
              {cur && <button disabled={p.saving} onClick={() => { if (confirm(`更新 preset「${cur.name}」?其他引用它的 cell 也會跟著變。`)) p.onSaveAntennaPreset(sel.cell, fields(), cur.name, cur.antenna_preset_uuid); }}>更新「{cur.name}」</button>}
              {sel.cell.ru?.antenna_override != null && <button className="ghost" disabled={p.saving} onClick={() => p.onAntennaFields(sel.cell, {})}>清除覆寫</button>}</div>); })()}
          <p className="muted small">噪聲係數 {sel.cell.ru?.noise_figure_db ?? '—'} dB · preset 清單在「網路元件」頁維護</p>
          <p className="muted small">max dBi 是描述用欄位,不進模擬 —— tr38901 元件的 8 dBi 已在 Sionna 輻射圖內。改 rows/cols/pattern/極化 會影響 MIMO 的通道矩陣;RSRP 與覆蓋來自預算好的通道快取,要一併反映得重跑 precompute。</p></>
        : sel?.kind === 'ue' ? <label><span>UE 天線</span><select value={sel.ue.f_antenna_preset_uuid ?? ''} onChange={(e) => p.onUeAntenna(sel.ue, e.target.value || null)}><option value="">(預設 1×1)</option>{p.presets.map((a) => <option key={a.antenna_preset_uuid} value={a.antenna_preset_uuid}>{a.name} — {a.rows}×{a.cols}</option>)}</select></label>
        : <>
          <div className="row head">場景層級天線 <span className="muted">一個 run 只能一組(Sionna 限制)</span></div>
          <label><span>gNB 陣列</span><select value={p.scene.f_gnb_antenna_preset_uuid ?? ''} onChange={(e) => p.onSceneAntenna('gnb', e.target.value || null)}><option value="">(未設 → 第一個 cell 的 RU preset / 1×1 tr38901)</option>{p.presets.map((a) => <option key={a.antenna_preset_uuid} value={a.antenna_preset_uuid}>{a.name} — {a.pattern} {a.rows}×{a.cols} {a.polarization}</option>)}</select></label>
          <label><span>UE 陣列</span><select value={p.scene.f_ue_antenna_preset_uuid ?? ''} onChange={(e) => p.onSceneAntenna('ue', e.target.value || null)}><option value="">(未設 → 第一個 UE 的 preset / 1×1 dipole)</option>{p.presets.map((a) => <option key={a.antenna_preset_uuid} value={a.antenna_preset_uuid}>{a.name} — {a.pattern} {a.rows}×{a.cols} {a.polarization}</option>)}</select></label>
          <p className="muted small">兩層 MIMO 需要:gNB 與 UE 都 ≥ 2 埠(建議 cross 極化)、SINR ≥ 15 dB、有流量。個別 cell / UE 的 preset 只在場景層級未設時當預設。</p>
          {p.onE2Block && (() => {
            // 多 gNB(2026-09-27):一個 gNB 一個 E2 node。釘住區塊 = 每個 gNB 的 gNB ID、meid、cell NCI 都固定。
            // 外部 Agent 要先拿這些識別去部署 xApp(E2 訂閱與 control 都用 meid + NCI 定位),識別浮動就訂不到。
            // 這裡把推導後的值逐一列出,不必去翻 API 才知道會給對方什麼。規格:docs/architecture/multi_gnb_plan.md D3。
            const block = p.scene.e2_block;
            const rows = block ? [...(p.gnbs ?? [])].sort((a, b) => (a.e2_index ?? 99) - (b.e2_index ?? 99)).map((g) => {
              const slot = 16 * block + (g.e2_index ?? 0);
              const gid = 0x000e00 | slot;
              return { name: g.name, idx: g.e2_index, gnb: `0x${gid.toString(16).padStart(6, '0')}`,
                       node: `gnb_208_095_${gid.toString(16).padStart(6, '0')}`, tag: (gid & 0xfff).toString(16).padStart(3, '0') };
            }) : [];
            return <>
              <div className="row head">Agent 介面 <span className="muted">E2 識別(給外部 Agent 部署 xApp)</span></div>
              {p.onCategory && <label><span>分類</span>
                <select value={p.scene.category ?? ''} onChange={(e) => p.onCategory!(e.target.value || null)}>
                  <option value="">(未宣告 → 依名稱前綴推:{catLabel(categoryOfScene(p.scene))})</option>
                  {CATEGORY_OPTIONS.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
                </select></label>}
              <label><span>E2 區塊</span>
                <input type="number" min={1} max={15} defaultValue={block ?? ''} placeholder="1–15,留空 = 啟動時動態配"
                       onBlur={(e) => { const v = e.target.value.trim(); const n = v === '' ? null : Number(v);
                                        if (n !== (block ?? null)) p.onE2Block!(n); }} /></label>
              {block
                ? <>
                    <p className="muted small">每個 gNB 一個 E2 node,每次啟動都一樣,可事先寫進 xApp 訂閱。代價:此場景同時只能跑一場。</p>
                    <table className="small"><thead><tr><th>gNB</th><th>#</th><th>gNB ID</th><th>E2 node</th><th>cell 前綴</th></tr></thead>
                      <tbody>{rows.map((r) => <tr key={r.name}><td>{r.name}</td><td>{r.idx ?? '—'}</td><td className="mono">{r.gnb}</td><td className="mono">{r.node}</td><td className="mono">{r.tag}:</td></tr>)}</tbody></table>
                  </>
                : <p className="muted small">未釘區塊 → 每次啟動的 gNB ID 與 cell NCI 都可能不同,xApp 無法事先訂閱。只有要給外部 Agent 用的場景才需要釘。</p>}
            </>; })()}</>)}
      {tab === 'ran' && <>
        {(sel?.kind === 'gnb' || sel?.kind === 'cell') && (() => { const g = sel.kind === 'gnb' ? sel.gnb : sel.gnb; const du = g.dus[0]; return <>
          <div className="row head">DU 設定模板 <span className="muted">{du?.name}</span></div>
          <label><span>模板</span><select value={du?.f_du_config_template_uuid ?? ''} onChange={(e) => du && p.onDu(du, { f_du_config_template_uuid: e.target.value || null })}><option value="">(服務預設)</option>{p.templates.map((t) => <option key={t.du_config_template_uuid} value={t.du_config_template_uuid}>{t.name} — {t.tdd_pattern} μ{t.numerology} {t.n_prb} PRB</option>)}</select></label>
          {du && <DuFields du={du} saving={p.saving} onDu={p.onDu} />}
          <label><span>進階:覆寫 JSON</span><textarea rows={4} value={f('du_override')} onChange={(e) => set('du_override', e.target.value)} /></label>
          <div className="actions"><button className="primary" disabled={p.saving || parse(f('du_override')) === undefined} onClick={() => du && p.onDu(du, { config_override: parse(f('du_override')) })}>套用 JSON</button></div>
          <div className="row head">A3 換手(gNB)<span className={`pill ${g.a3_enabled ? 'good' : 'fair'}`}>{g.a3_enabled ? '已開啟' : '關閉'}</span></div>
          <label className="stack"><span>啟用 A3 自動換手</span>
            <input type="checkbox" checked={!!g.a3_enabled} disabled={p.saving}
              onChange={(e) => p.onGnb(g, e.target.checked
                ? { a3_enabled: true, a3_offset_db: num('a3_offset_db') ?? 3, a3_hys_db: num('a3_hys_db') ?? 1, a3_ttt_ms: num('a3_ttt_ms') ?? 320 }
                : { a3_enabled: false })} /></label>
          {!g.a3_enabled && <p className="muted small">關閉時 UE 不會主動換手,只能在斷線後重新駐留。</p>}
          <div className="xyz"><Field k="a3_offset_db" label="offset dB" v={f('a3_offset_db')} set={set} type="number" /><Field k="a3_hys_db" label="hys dB" v={f('a3_hys_db')} set={set} type="number" /><Field k="a3_ttt_ms" label="TTT ms" v={f('a3_ttt_ms')} set={set} type="number" /></div>
          <div className="actions"><button className="primary" disabled={p.saving} onClick={() => p.onGnb(g, { a3_enabled: true, a3_offset_db: num('a3_offset_db'), a3_hys_db: num('a3_hys_db'), a3_ttt_ms: num('a3_ttt_ms') })}>儲存 A3</button><button disabled={p.saving} onClick={() => p.onGnb(g, { a3_enabled: false })}>停用 A3</button></div></>; })()}
        {p.showRun !== false && <>
        <div className="row head">Run 設定 <span className="muted">{p.run ? p.run.status : '尚無 run(儲存即建 draft)'}</span></div>
        <label><span>模式</span><select value={p.run?.mode ?? 'live'} onChange={(e) => p.onRun({ mode: e.target.value as SceneRun['mode'] })}><option value="live">live(Sionna 即時)</option><option value="cached">cached(預算 npz)</option></select></label>
        <label><span>倍速</span><input type="number" defaultValue={p.run?.speed_x ?? 1} onBlur={(e) => Number(e.target.value) !== (p.run?.speed_x ?? 1) && p.onRun({ speed_x: Number(e.target.value) })} /></label>
        <label><span>sim_dt ms</span><input type="number" defaultValue={p.run?.sim_dt_ms ?? 500} onBlur={(e) => Number(e.target.value) !== (p.run?.sim_dt_ms ?? 500) && p.onRun({ sim_dt_ms: Number(e.target.value) })} /></label>
        <label><span>時長 s</span><input type="number" defaultValue={p.run?.duration_sec ?? 3600} onBlur={(e) => Number(e.target.value) !== (p.run?.duration_sec ?? 3600) && p.onRun({ duration_sec: Number(e.target.value) })} /></label>
        {/* 2026-09-20:上面三個欄位是「值有變才存」,沒有 run 時比較對象就是同一組預設值 —— 
            接受預設值的人永遠建不出 run(啟動前檢查卡在「還沒有 run 設定」)。補一個明確的按鈕。 */}
        <div className="actions"><button className="primary" disabled={p.saving}
          onClick={() => p.onRun({ mode: p.run?.mode ?? 'live', speed_x: p.run?.speed_x ?? 1,
                                   sim_dt_ms: p.run?.sim_dt_ms ?? 500, duration_sec: p.run?.duration_sec ?? 3600 })}>
          {p.run ? '儲存 Run 設定' : '建立 Run 設定'}</button></div>
        <div className="row head">Run knobs <span className="muted">inter_freq / cell_quotas / tx_power…</span></div>
        <ul className="knobs">{p.knobs.map((k) => <li key={k.run_knob_uuid}><b className="mono">{k.key}</b><span className="mono small">{typeof k.value === 'string' ? k.value : JSON.stringify(k.value)}</span><button className="ghost" onClick={() => p.onRemoveKnob(k.run_knob_uuid)}>×</button></li>)}</ul>
        <form className="inline" onSubmit={(e) => { e.preventDefault(); if (knobVal.trim()) { p.onKnob(knobKey, knobVal.trim()); setKnobVal(''); } }}><select value={knobKey} onChange={(e) => setKnobKey(e.target.value)}>{RUN_KNOB_KEYS.map((k) => <option key={k}>{k}</option>)}</select><input placeholder="值(JSON 或字串)" value={knobVal} onChange={(e) => setKnobVal(e.target.value)} /><button type="submit" disabled={p.saving}>設定</button></form></>}
      </>}
      {p.message && <p className="msg">{p.message}</p>}
    </aside>
  );
}
