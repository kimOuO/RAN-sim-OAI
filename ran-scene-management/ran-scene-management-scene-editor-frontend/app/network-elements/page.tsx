'use client';
import { useState } from 'react';
import { ANTENNA_PATTERNS, BF_METHODS, POLARIZATIONS, RU_CATEGORIES } from '@/config';
import { useNetworkElementsPage, type NeTab } from '@/hooks/feature/useNetworkElementsPage';

type Col = { k: string; l: string; t?: 'number' | 'text' | 'bool' | 'select' | 'ref'; opts?: readonly string[]; ref?: 'du' | 'antenna';
  /** 唯讀推導欄(不可編輯),例如由三層欄位算出的元件總數 */
  calc?: (r: Record<string, unknown>) => string;
  /** 存得下去但模擬不讀的欄位(描述用)。表頭加記號,避免以為調了會有效果 */
  inert?: string };
const nPol = (p: unknown) => (p === 'cross' || p === 'VH' ? 2 : 1);
const elemCount = (r: Record<string, unknown>) =>
  Number(r.panels_mg ?? 1) * Number(r.panels_ng ?? 1) * Number(r.rows ?? 1) * Number(r.cols ?? 1) * nPol(r.polarization);
const GNB: Col[] = [{ k: 'name', l: '名稱' }, { k: 'source', l: '來源' }, { k: 'plmn_mcc', l: 'MCC' }, { k: 'plmn_mnc', l: 'MNC' }, { k: 'band', l: 'band' }, { k: 'center_frequency_ghz', l: 'GHz', t: 'number' }, { k: 'bandwidth_mhz', l: 'BW MHz', t: 'number' }, { k: 'power_dbm', l: 'dBm', t: 'number' }, { k: 'tilt_deg', l: '下傾°', t: 'number' }, { k: 'cells_per_gnb', l: 'cell 數', t: 'number' }, { k: 'azimuth_step_deg', l: '方位步°', t: 'number' }, { k: 'a3_enabled', l: 'A3', t: 'bool' }, { k: 'a3_offset_db', l: 'A3 off', t: 'number' }, { k: 'a3_hys_db', l: 'hys', t: 'number' }, { k: 'a3_ttt_ms', l: 'TTT', t: 'number' }, { k: 'f_du_config_template_uuid', l: 'DU 模板', t: 'ref', ref: 'du' }, { k: 'f_antenna_preset_uuid', l: '天線', t: 'ref', ref: 'antenna' }, { k: 'notes', l: '備註' }];
const ANT: Col[] = [
  { k: 'name', l: '名稱' },
  // ── 元件層(TR 38.901 §7.3)────────────────────────────────
  { k: 'pattern', l: '圖樣', t: 'select', opts: ANTENNA_PATTERNS },
  { k: 'rows', l: 'M 列', t: 'number' }, { k: 'cols', l: 'N 行', t: 'number' },
  { k: 'polarization', l: '極化', t: 'select', opts: POLARIZATIONS },
  { k: 'panels_mg', l: '面板 Mg', t: 'number' }, { k: 'panels_ng', l: '面板 Ng', t: 'number' },
  { k: 'v_spacing', l: 'dV λ', t: 'number' }, { k: 'h_spacing', l: 'dH λ', t: 'number' },
  { k: 'max_gain_dbi', l: '增益 dBi', t: 'number', inert: 'tr38901 元件的 8 dBi 已包含在 Sionna 的輻射圖裡,模擬不另外讀這個值(讀了會重複計算)。此欄僅供辨識 preset。' },
  { k: '_elem', l: '元件數', calc: (r) => `${elemCount(r)}` },
  // ── TRX 層(TR 38.901 式 7.3-1 虛擬化)──────────────────────
  { k: 'trx_v_group', l: '每TRX垂直', t: 'number' }, { k: 'trx_count', l: 'TRX', t: 'number' },
  { k: 'electrical_tilt_deg', l: '電子下傾°', t: 'number' },
  // ── 埠層(TS 38.214 Type I)────────────────────────────────
  { k: 'csi_ports', l: 'CSI 埠', t: 'number' },
  { k: '_layout', l: '(N1,N2)', calc: (r) => `(${r.port_n1 ?? 0},${r.port_n2 ?? 0})` },
  { k: 'port_n1', l: 'N1', t: 'number' }, { k: 'port_n2', l: 'N2', t: 'number' },
  // ── O-RAN 類別 / beamforming ─────────────────────────────
  { k: 'ru_category', l: 'O-RU Cat', t: 'select', opts: RU_CATEGORIES },
  { k: 'bf_method', l: 'BF 方法', t: 'select', opts: BF_METHODS, inert: '會存進 RU 的 AntennaConfig,但目前沒有任何邏輯讀它(規劃中的階段 B1/B2 才會用到)。' },
  { k: 'gob_az_beams', l: 'GoB 方位', t: 'number' }, { k: 'gob_el_beams', l: 'GoB 仰角', t: 'number' },
];
const DU: Col[] = [{ k: 'name', l: '名稱' }, { k: 'tdd_pattern', l: 'TDD' }, { k: 'numerology', l: 'μ', t: 'number' }, { k: 'n_prb', l: 'PRB', t: 'number' }, { k: 'min_prb', l: 'min PRB', t: 'number' }, { k: 'pf_alpha', l: 'PF α', t: 'number' }, { k: 'target_bler', l: 'BLER', t: 'number' }, { k: 'rlc_discard_timer_ms', l: 'discard ms', t: 'number' }, { k: 'rlc_tx_maxsize_bytes', l: 'RLC tx B', t: 'number' }, { k: 'harq_max_retx', l: 'HARQ', t: 'number' }, { k: 'qos_gbr_first', l: 'GBR 優先', t: 'bool' }, { k: 'gbr_max_share', l: 'GBR 上限', t: 'number' }];
const MAT: Col[] = [{ k: 'key', l: 'key' }, { k: 'itu_id', l: 'ITU-R P.2040' }, { k: 'freq_range_ghz', l: '頻率範圍 GHz' }, { k: 'notes', l: '備註' }];
const TABS: { k: NeTab; l: string; d: string }[] = [{ k: 'gnb', l: 'gNB 模板', d: 'gNB 級參數組(PLMN、A3、cell RF 預設、綁 DU 模板與天線)。場景放 gNB 時自動套「OAI 對齊預設」;gNB 屬性頁可套用其他模板、或把現場 gNB 存成 / 更新模板。' }, { k: 'antenna', l: '天線陣列', d: '三層模型:元件層(TR 38.901 §7.3 面板 Mg×Ng×M×N×P)→ TRX 層(每個 TXRU 垂直帶幾片元件、電子下傾用式 7.3-1)→ 埠層(TS 38.214 Type I 的 CSI-RS 埠與 (N1,N2))。O-RU Cat A = precoding 在 O-DU;Cat B = O-RU 自己做 beamforming。' }, { k: 'du', l: 'DU 設定模板', d: 'TDD、numerology、PRB、PF、BLER 目標、RLC / HARQ;gNB 的 DU 選一個套用' }, { k: 'material', l: '建築材質', d: 'ITU-R P.2040 材質,建築 / 場景地面可選' }];

/** 網路元件管理:表格 + 內嵌編輯列。呈現層;寫回交 hook。 */
export default function NetworkElementsPage() {
  const p = useNetworkElementsPage();
  const [form, setForm] = useState<Record<string, string>>({});
  const cols = p.tab === 'gnb' ? GNB : p.tab === 'antenna' ? ANT : p.tab === 'du' ? DU : MAT;
  const rows = (p.tab === 'gnb' ? p.gnbs : p.tab === 'antenna' ? p.antennas : p.tab === 'du' ? p.templates : p.materials) as unknown as Record<string, unknown>[];
  const idKey = p.tab === 'gnb' ? 'gnb_config_template_uuid' : p.tab === 'antenna' ? 'antenna_preset_uuid' : p.tab === 'du' ? 'du_config_template_uuid' : 'material_uuid';
  const startEdit = (r: Record<string, unknown> | null) => { p.setEditing(r ? String(r[idKey]) : 'new'); setForm(Object.fromEntries(cols.map((c) => [c.k, r ? (r[c.k] == null ? '' : String(r[c.k])) : (c.t === 'bool' ? 'false' : '')]))); };
  const body = () => Object.fromEntries(cols.map((c) => [c.k, c.t === 'number' ? Number(form[c.k] || 0) : c.t === 'bool' ? form[c.k] === 'true' : c.t === 'ref' ? (form[c.k] || null) : form[c.k] ?? '']));
  const refName = (c: Col, v: unknown) => c.ref === 'du' ? p.templates.find((t) => t.du_config_template_uuid === v)?.name : p.antennas.find((a) => a.antenna_preset_uuid === v)?.name;
  const save = () => { const uuid = p.editing === 'new' ? null : p.editing; if (p.tab === 'gnb') p.saveGnb(uuid, body()); else if (p.tab === 'antenna') p.saveAntenna(uuid, body()); else if (p.tab === 'du') p.saveTemplate(uuid, body()); else p.saveMaterial(uuid, body()); };
  const cellInput = (c: Col) => c.calc ? <span className="muted">—</span> : c.t === 'ref' ? <select value={form[c.k] ?? ''} onChange={(e) => setForm({ ...form, [c.k]: e.target.value })}><option value="">(無)</option>{(c.ref === 'du' ? p.templates.map((t) => [t.du_config_template_uuid, t.name]) : p.antennas.map((a) => [a.antenna_preset_uuid, a.name])).map(([v, n]) => <option key={v} value={v}>{n}</option>)}</select>
    : c.t === 'select' ? <select value={form[c.k] ?? ''} onChange={(e) => setForm({ ...form, [c.k]: e.target.value })}>{c.opts!.map((o) => <option key={o}>{o}</option>)}</select>
    : c.t === 'bool' ? <select value={form[c.k] ?? 'false'} onChange={(e) => setForm({ ...form, [c.k]: e.target.value })}><option value="true">是</option><option value="false">否</option></select>
    : <input type={c.t === 'number' ? 'number' : 'text'} step="any" value={form[c.k] ?? ''} onChange={(e) => setForm({ ...form, [c.k]: e.target.value })} />;
  const editRow = <tr className="edit"><td className="muted">{p.editing === 'new' ? '新增' : '編輯'}</td>{cols.map((c) => <td key={c.k}>{cellInput(c)}</td>)}<td className="acts"><button className="primary" disabled={p.busy} onClick={save}>儲存</button><button className="ghost" onClick={() => p.setEditing(null)}>取消</button></td></tr>;
  return (
    <section className="shell page wide">
      <header className="pagehead"><h1>網路元件</h1><span className="muted">可重用的設定資源;場景裡的 cell / DU / 建築引用這些</span></header>
      <div className="tabs big">{TABS.map((t) => <button key={t.k} className={p.tab === t.k ? 'on' : ''} onClick={() => { p.setTab(t.k); p.setEditing(null); }}>{t.l}</button>)}</div>
      <p className="muted">{TABS.find((t) => t.k === p.tab)?.d}</p>
      {cols.some((c) => c.inert) && <p className="muted small">標 ° 的欄位存得下去但模擬不讀(滑過看原因)。</p>}
      <div className="card">
        <div className="tablewrap"><table className="ne"><thead><tr><th></th>{cols.map((c) => <th key={c.k} title={c.inert}>{c.l}{c.inert && <span className="muted"> °</span>}</th>)}<th></th></tr></thead>
          <tbody>
            {p.editing === 'new' && editRow}
            {rows.map((r) => { const id = String(r[idKey]); return p.editing === id ? <tr key={id} className="edit"><td className="muted">編輯</td>{cols.map((c) => <td key={c.k}>{cellInput(c)}</td>)}<td className="acts"><button className="primary" disabled={p.busy} onClick={save}>儲存</button><button className="ghost" onClick={() => p.setEditing(null)}>取消</button></td></tr>
              : <tr key={id}><td className="mono muted small" title={id}>{id.slice(-6)}</td>{cols.map((c) => <td key={c.k}>{c.t === 'bool' ? (r[c.k] ? '是' : '否') : c.t === 'ref' ? (refName(c, r[c.k]) ?? <span className="muted">—</span>) : c.calc ? c.calc(r) : String(r[c.k] ?? '')}</td>)}<td className="acts"><button className="ghost" onClick={() => startEdit(r)}>編輯</button>{p.tab !== 'material' && <button className="ghost danger" onClick={() => { if (confirm('刪除?')) (p.tab === 'gnb' ? p.removeGnb : p.tab === 'antenna' ? p.removeAntenna : p.removeTemplate)(id); }}>刪除</button>}</td></tr>; })}
          </tbody></table></div>
        <div className="actions"><button className="primary" onClick={() => startEdit(null)} disabled={p.editing === 'new'}>+ 新增{TABS.find((t) => t.k === p.tab)?.l}</button>{p.msg && <span className="msg">{p.msg}</span>}</div>
      </div>
    </section>
  );
}
