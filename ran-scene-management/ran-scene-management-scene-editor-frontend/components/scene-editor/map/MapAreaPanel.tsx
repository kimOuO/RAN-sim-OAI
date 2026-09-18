'use client';
import { MAX_MAP_AREA_M2 } from '@/config';
import type { MapBuilder } from '@/hooks/feature/useMapBuilder';

/** 地圖左欄:搜尋地標 → 範圍(面積、頂點)→ 重畫 / 讀取建築 */
export function MapAreaPanel({ m, onBack }: { m: MapBuilder; onBack: () => void }) {
  const tooBig = m.area > MAX_MAP_AREA_M2;
  return (
    <>
      <button className="link" onClick={onBack}>← 換場景來源</button>
      <div className="mapfetch">
        <div className="row head">1. 找地點</div>
        <form onSubmit={(e) => { e.preventDefault(); void m.search(); }} className="inline">
          <input placeholder="地標,例:台科大、台北車站" value={m.query} onChange={(e) => m.setQuery(e.target.value)} />
          <button type="submit" disabled={m.busy != null || !m.query.trim()}>{m.busy === 'geocode' ? '…' : '搜尋'}</button>
        </form>
        {m.results.length > 1 && <ul className="georesults">{m.results.map((r) =>
          <li key={r.display_name}><button className="link" onClick={() => m.pick(r)} title={r.display_name}>{r.display_name}</button></li>)}</ul>}
      </div>
      <div className="mapfetch">
        <div className="row head">2. 調整範圍</div>
        {m.polygon.length >= 3
          ? <p className="small">{m.polygon.length} 個頂點 · <b className={tooBig ? 'err' : ''}>{m.area >= 1e5 ? `${(m.area / 1e6).toFixed(2)} km²` : `${Math.round(m.area).toLocaleString()} m²`}</b>
            {tooBig && <span className="err"> · 超過上限 {MAX_MAP_AREA_M2 / 1e6} km²</span>}</p>
          : <p className="muted small">搜尋地標後會自動框一個範圍,或自己畫。</p>}
        <p className="muted small">拖曳頂點移動、拖曳邊上的小點新增頂點、雙擊頂點刪除。</p>
        {m.drawing
          ? <div className="two"><button onClick={m.finishDraw} disabled={m.drawing.length < 3}>完成({m.drawing.length})</button><button onClick={m.cancelDraw}>取消</button></div>
          : <button className="wide" onClick={m.startDraw}>重新畫多邊形</button>}
      </div>
      <div className="mapfetch">
        <div className="row head">3. 讀取建築</div>
        <button className="wide primary" disabled={m.polygon.length < 3 || tooBig || m.busy != null || m.drawing != null} onClick={() => void m.preview()}>
          {m.busy === 'preview' ? '從 OSM 讀取中…' : m.buildings.length ? '重新讀取範圍內建築' : '讀取範圍內建築'}</button>
        {m.stale && <p className="msg small">範圍改過了,重新讀取才會套用新範圍(材質設定會重置)。</p>}
        {m.buildings.length > 0 && <p className="muted small">{m.buildings.length} 棟;在右側逐棟設定材質。</p>}
      </div>
      {m.error && <p className="err small">{m.error}</p>}
    </>
  );
}
