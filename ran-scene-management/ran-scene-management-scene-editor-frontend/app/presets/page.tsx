'use client';
import { useAsync } from '@/hooks/base/useAsync';
import { listAntennaPresets, listDuConfigTemplates, listMaterials } from '@/services/api/presets';

export default function PresetsPage() {
  const a = useAsync(listAntennaPresets, []); const m = useAsync(listMaterials, []); const d = useAsync(listDuConfigTemplates, []);
  return (
    <section className="page">
      <h1>資源庫</h1>
      <h2>天線 preset</h2>
      <table><thead><tr><th>名稱</th><th>來源</th><th>pattern</th><th>陣列</th><th>極化</th><th>間距 λ</th><th>max dBi</th></tr></thead>
        <tbody>{(a.data ?? []).map((p) => <tr key={p.antenna_preset_uuid}><td>{p.name}</td><td>{p.source}</td><td>{p.pattern}</td><td>{p.rows}×{p.cols}</td><td>{p.polarization}</td><td>{p.v_spacing}/{p.h_spacing}</td><td>{p.max_gain_dbi}</td></tr>)}</tbody></table>
      <h2>材質</h2>
      <table><thead><tr><th>key</th><th>ITU</th><th>頻率範圍</th></tr></thead><tbody>{(m.data ?? []).map((x) => <tr key={x.material_uuid}><td>{x.key}</td><td>{x.itu_id}</td><td>{x.freq_range_ghz}</td></tr>)}</tbody></table>
      <h2>DU 設定模板</h2>
      <table><thead><tr><th>名稱</th><th>TDD</th><th>μ</th><th>PRB</th><th>min PRB</th><th>PF α</th><th>BLER</th><th>discard ms</th></tr></thead>
        <tbody>{(d.data ?? []).map((x) => <tr key={x.du_config_template_uuid}><td>{x.name}</td><td>{x.tdd_pattern}</td><td>{x.numerology}</td><td>{x.n_prb}</td><td>{x.min_prb}</td><td>{x.pf_alpha}</td><td>{x.target_bler}</td><td>{x.rlc_discard_timer_ms}</td></tr>)}</tbody></table>
      {[a, m, d].some((x) => x.status === 'loading') && <p className="muted">載入中…</p>}
    </section>
  );
}
