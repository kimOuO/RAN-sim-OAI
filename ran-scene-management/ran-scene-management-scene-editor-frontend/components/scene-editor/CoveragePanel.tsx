'use client';
import { CELL_COLORS, COVERAGE_SCALE, RAMP_CSS } from '@/components/scene-canvas/CoverageLayer';
import type { CoverageMode, CoverageState } from '@/hooks/feature/useCoverage';

const MODES: { k: CoverageMode; l: string }[] = [{ k: 'sinr', l: 'SINR' }, { k: 'rsrp', l: 'RSRP' }, { k: 'cell', l: '最佳 cell' }];
/** 步驟 2:覆蓋熱圖預覽(確認天線方向、盲區、同頻干擾) */
export function CoveragePanel({ c }: { c: CoverageState }) {
  const r = c.result;
  const stat = (() => { if (!r) return null; const v = r.summary.sinr_db.flat().filter((x): x is number => x != null); if (!v.length) return null; v.sort((a, b) => a - b);
    return { med: v[Math.floor(v.length / 2)], low: v.filter((x) => x < 0).length / v.length, n: v.length }; })();
  return (
    <div className="coverage">
      <div className="row head">覆蓋熱圖 <span className="muted">GPU 光追,不影響執行中的 run</span></div>
      <div className="two">
        <label className="stack"><span>取樣高度 m</span><input type="number" step={0.1} value={c.height} onChange={(e) => c.setHeight(Number(e.target.value))} /></label>
        <label className="stack"><span>格距 m(空 = 自動)</span><input type="number" step={0.25} value={c.step ?? ''} onChange={(e) => c.setStep(e.target.value === '' ? null : Number(e.target.value))} /></label>
      </div>
      <div className="actions"><button className="primary" disabled={c.busy} onClick={c.run}>{c.busy ? '計算中…' : r ? '重新計算' : '計算覆蓋'}</button>
        {r && <label className="check-inline"><input type="checkbox" checked={c.show} onChange={(e) => c.setShow(e.target.checked)} /> 顯示</label>}</div>
      {c.error && <p className="err small">{c.error}</p>}
      {r && <>
        <div className="chips">{MODES.map((m) => <button key={m.k} className={`chip ${c.mode === m.k ? 'on' : ''}`} onClick={() => c.setMode(m.k)}>{m.l}</button>)}</div>
        <label className="stack"><span>不透明度</span><input type="range" min={0.1} max={1} step={0.05} value={c.opacity} onChange={(e) => c.setOpacity(Number(e.target.value))} /></label>
        {c.mode === 'cell'
          ? <div className="legend">{r.summary.cell_names.map((n, i) => <span key={n}><i style={{ background: CELL_COLORS[i % CELL_COLORS.length] }} />{n}</span>)}</div>
          : <div className="ramp"><div style={{ background: RAMP_CSS }} /><span>{COVERAGE_SCALE[c.mode].min}</span><span>{COVERAGE_SCALE[c.mode].max} {COVERAGE_SCALE[c.mode].unit}</span></div>}
        <p className="muted small">{r.grid.n_cols}×{r.grid.n_rows} 格 · 格距 {r.grid.x_step} m · {(r.compute_ms / 1000).toFixed(1)} s
          {stat && <> · SINR 中位 {stat.med.toFixed(1)} dB · &lt;0 dB 佔 {(stat.low * 100).toFixed(0)}%</>}</p>
        <p className="muted small">熱圖是理想光追(不含 29 dB 失真上限與 UE 天線以外的損耗),用來看相對分布。</p>
      </>}
    </div>
  );
}
