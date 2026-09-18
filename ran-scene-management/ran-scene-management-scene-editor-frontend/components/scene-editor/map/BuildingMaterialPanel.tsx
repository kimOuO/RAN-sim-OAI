'use client';
import { useEffect, useState } from 'react';
import { MATERIAL_COLORS, MATERIAL_LABELS } from '@/config';
import type { MapBuilder } from '@/hooks/feature/useMapBuilder';
import type { Material } from '@/types/registry';

/** 地圖右欄:以建築為單位設定材質 / 高度 / 排除,最後產生場景 */
export function BuildingMaterialPanel({ m, materials, defaultName }: { m: MapBuilder; materials: Material[]; defaultName: string }) {
  const [name, setName] = useState(defaultName);
  useEffect(() => setName(defaultName), [defaultName]);
  const sel = m.buildings.filter((b) => m.selected.has(b.id));
  const one = sel.length === 1 ? sel[0] : null;
  const same = <K extends 'material' | 'height_m'>(k: K) => (sel.length && sel.every((b) => b[k] === sel[0][k]) ? String(sel[0][k]) : '');
  const label = (k: string) => MATERIAL_LABELS[k] ?? k;
  return (
    <aside className="panel">
      <div className="panel-head"><h3>建築材質</h3></div>
      {!m.buildings.length ? <p className="muted small">讀取範圍內建築後,點地圖上的建築設定材質(Shift / Ctrl 多選)。</p> : <>
        <div className="matlegend">{Object.entries(m.counts).sort((a, b) => b[1] - a[1]).map(([k, n]) =>
          <button key={k} className="link" onClick={() => m.selectByMaterial(k)} title="選取這種材質的全部建築">
            <i style={{ background: MATERIAL_COLORS[k] ?? '#999' }} />{label(k)} {n}</button>)}</div>
        <div className="two"><button onClick={m.selectAll}>全選</button><button onClick={m.clearSelection} disabled={!sel.length}>清除選取</button></div>

        <h4>{one ? one.name : sel.length ? `已選 ${sel.length} 棟` : '未選取'}</h4>
        {sel.length > 0 && <>
          <label><span>材質</span>
            <select value={same('material')} onChange={(e) => m.patchSelected({ material: e.target.value })}>
              {!same('material') && <option value="">(多種)</option>}
              {materials.map((x) => <option key={x.key} value={x.key}>{label(x.key)}({x.itu_id})</option>)}
            </select></label>
          <label><span>頂高 (m)</span>
            <input type="number" min={1} step={0.5} value={same('height_m')} placeholder="(多種)"
              onChange={(e) => { const v = Number(e.target.value); if (v > 0) m.patchSelected({ height_m: v, height_known: true }); }} /></label>
          {one && <p className="muted small">底高 {one.base_m} m · 高度{one.height_known ? '來自 OSM / 手動' : '為預設值(OSM 沒有樓層資料)'}</p>}
          <button className="wide" onClick={() => m.patchSelected({ excluded: !sel.every((b) => b.excluded) })}>
            {sel.every((b) => b.excluded) ? '納入場景' : '排除(不放進場景)'}</button>
        </>}

        <h4>產生場景</h4>
        <label><span>幾何名稱</span><input value={name} onChange={(e) => setName(e.target.value)} /></label>
        <p className="muted small">{m.included.length} 棟會放進場景{m.buildings.length > m.included.length ? `(排除 ${m.buildings.length - m.included.length} 棟)` : ''}。產生後進入 3D,接著放網路元件與 UE。</p>
        <button className="wide primary" disabled={!!m.blocked || m.busy != null || !name.trim()} title={m.blocked ?? ''} onClick={() => void m.build(name.trim())}>
          {m.busy === 'build' ? '產生中…' : '產生場景 → 3D'}</button>
        {m.blocked && <p className="muted small">{m.blocked}</p>}
      </>}
    </aside>
  );
}
