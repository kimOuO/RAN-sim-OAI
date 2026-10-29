'use client';
import { useState } from 'react';
import { MATERIAL_COLORS, MATERIAL_LABELS } from '@/config';
import type { SceneMesh } from '@/services/api/scenes';

export function GeometryObjectList({ meshes, selectedId, onSelect }: { meshes: SceneMesh[]; selectedId: string | null; onSelect: (mesh: SceneMesh) => void }) {
  const [query, setQuery] = useState('');
  if (!meshes.length) return null;
  const shown = meshes.filter((m) => `${m.name} ${m.material} ${MATERIAL_LABELS[m.material.replace(/^itu_/, '')] ?? ''}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="tree">
    <div className="row head">場景模型 <span className="muted">{meshes.filter((m) => m.kind === 'building').length} 棟建築</span></div>
    <input aria-label="搜尋建築" placeholder="搜尋建築或材質" value={query} onChange={(e) => setQuery(e.target.value)} style={{ width: '100%' }} />
    <div style={{ maxHeight: 280, overflowY: 'auto', marginTop: 6 }}>
      {shown.map((m) => <button key={m.shape_id} className={`row sub${selectedId === m.shape_id ? ' sel' : ''}`} disabled={m.too_large} onClick={() => onSelect(m)}>
        <span style={{ color: MATERIAL_COLORS[m.material.replace(/^itu_/, '')] ?? '#8f98a3' }}>▦ </span>{m.kind === 'surface' ? '地面' : m.name}<span className="muted small"> · {MATERIAL_LABELS[m.material.replace(/^itu_/, '')] ?? m.material}</span>
      </button>)}
      {!shown.length && <p className="muted small">沒有符合的建築</p>}
    </div>
    <p className="muted small">點 3D 建築或上方清單，再到右側修改材質。</p>
  </div>;
}
