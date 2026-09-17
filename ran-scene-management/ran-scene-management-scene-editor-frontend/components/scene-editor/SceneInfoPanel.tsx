'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import type { Scene, SceneTree } from '@/types/registry';

interface GeoSource { label: string; geometry_scene_id: string; geometry_source: unknown }
interface Props {
  tree: SceneTree; saving: boolean; sources: GeoSource[];
  onSave: (f: Partial<Scene>) => void; onDuplicate: (name: string) => Promise<string | null>; onOpen: (sceneUuid: string) => void;
}
/** 步驟 1:場景基本資料 + 幾何來源(掃描模型 / 建築盒 / OSM)+ 複製場景 */
export function SceneInfoPanel({ tree, saving, sources, onSave, onDuplicate, onOpen }: Props) {
  const sc = tree.scene;
  const [f, setF] = useState({ name: sc.name, description: sc.description ?? '', lat: String(sc.origin_lat ?? ''), lon: String(sc.origin_lon ?? '') });
  useEffect(() => setF({ name: sc.name, description: sc.description ?? '', lat: String(sc.origin_lat ?? ''), lon: String(sc.origin_lon ?? '') }), [sc]);
  const geo = sc.geometry_source as { type?: string; path?: string } | null;
  const cur = geo?.type ? `${geo.type}${geo.path ? ` · ${geo.path.split('/').pop()}` : ''}` : '建築盒 / OSM(buildings_json)';
  const pick = (i: string) => { if (i === '') { if (confirm('改回用建築盒 / OSM 建模?掃描模型會被移除。')) onSave({ geometry_source: null, geometry_scene_id: '' }); return; }
    const s = sources[Number(i)]; if (s && confirm(`把幾何來源換成「${s.label}」?`)) onSave({ geometry_source: s.geometry_source, geometry_scene_id: s.geometry_scene_id }); };
  return (
    <div className="sceneinfo">
      <div className="row head">場景資料</div>
      <label className="stack"><span>名稱</span><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
      <label className="stack"><span>說明</span><textarea rows={2} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></label>
      <div className="two"><label className="stack"><span>原點緯度</span><input type="number" value={f.lat} onChange={(e) => setF({ ...f, lat: e.target.value })} /></label>
        <label className="stack"><span>原點經度</span><input type="number" value={f.lon} onChange={(e) => setF({ ...f, lon: e.target.value })} /></label></div>
      <div className="actions"><button className="primary" disabled={saving} onClick={() => onSave({ name: f.name, description: f.description, origin_lat: f.lat === '' ? null : Number(f.lat), origin_lon: f.lon === '' ? null : Number(f.lon) })}>儲存</button>
        <button disabled={saving} onClick={async () => { const n = prompt('複製成新場景,名稱:', `${sc.name}_copy`); if (!n) return; const id = await onDuplicate(n); if (id && confirm('已複製,要打開新場景嗎?')) onOpen(id); }}>複製場景</button></div>
      <div className="row head">幾何來源 <span className="muted">傳播計算用</span></div>
      <p className="small">目前:<span className="mono">{cur}</span></p>
      <label className="stack"><span>換成</span><select value="-" onChange={(e) => pick(e.target.value)}>
        <option value="-" disabled>選一個…</option><option value="">建築盒 / OSM(自己拉)</option>
        {sources.map((s, i) => <option key={i} value={i}>{s.label}</option>)}</select></label>
      <p className="muted small">匯入劇本 JSON 或新的掃描模型:<Link href="/imports">匯入頁</Link>。掃描模型只在傳播計算使用,畫布上以網格表示。</p>
    </div>
  );
}
