'use client';
import type { GeocodeResult } from '@/types/geometry';
interface Props { query: string; results: GeocodeResult[]; picked: GeocodeResult | null; busy: string | null; onQuery: (q: string) => void; onSearch: () => void; onPick: (g: GeocodeResult) => void; onFetch: () => void; }
/** 從網路拉場景:地標 → OSM 建築 footprint(building-geometry-ingest) */
export function MapFetchPanel({ query, results, picked, busy, onQuery, onSearch, onPick, onFetch }: Props) {
  return (
    <div className="mapfetch">
      <div className="row head">地圖(OpenStreetMap)</div>
      <form onSubmit={(e) => { e.preventDefault(); onSearch(); }} className="inline"><input placeholder="地標,例:台科大" value={query} onChange={(e) => onQuery(e.target.value)} /><button type="submit" disabled={busy != null || !query.trim()}>{busy === 'geocode' ? '…' : '搜尋'}</button></form>
      {results.length > 0 && <select value={picked?.display_name ?? ''} onChange={(e) => { const g = results.find((r) => r.display_name === e.target.value); if (g) onPick(g); }}>{results.map((r) => <option key={r.display_name} value={r.display_name}>{r.display_name}</option>)}</select>}
      {picked && <p className="muted small">bbox {picked.bbox.min_lat.toFixed(4)},{picked.bbox.min_lon.toFixed(4)} → {picked.bbox.max_lat.toFixed(4)},{picked.bbox.max_lon.toFixed(4)}</p>}
      <button className="wide primary" disabled={!picked || busy != null} onClick={onFetch}>{busy === 'generate' ? '抓 OSM 中(1–3 分鐘)…' : '拉建築到場景'}</button>
    </div>
  );
}
