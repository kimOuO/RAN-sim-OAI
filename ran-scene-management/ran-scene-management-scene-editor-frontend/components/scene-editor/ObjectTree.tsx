'use client';
import type { Selection } from '@/hooks/feature/useSceneEditorPage';
import type { SceneTree } from '@/types/registry';

export function ObjectTree({ tree, selection, onSelect }: { tree: SceneTree; selection: Selection; onSelect: (s: Selection) => void }) {
  const isSel = (k: string, id: string) => (selection?.kind === 'gnb' && k === 'gnb' && selection.gnb.gnb_uuid === id) || (selection?.kind === 'cell' && k === 'cell' && selection.cell.cell_uuid === id) || (selection?.kind === 'ue' && k === 'ue' && selection.ue.ue_uuid === id) || (selection?.kind === 'building' && k === 'building' && selection.building.building_uuid === id);
  const nCell = tree.gnbs.reduce((n, g) => n + g.dus.reduce((m, d) => m + d.cells.length, 0), 0);
  return (
    <div className="tree">
      <div className="row head">物件 <span className="muted">{tree.gnbs.length} gNB · {nCell} cell · {tree.ues.length} UE · {tree.buildings.length} 建築</span></div>
      {tree.gnbs.map((g) => (
        <div key={g.gnb_uuid} className="node">
          <button className={isSel('gnb', g.gnb_uuid) ? 'row sel' : 'row'} onClick={() => onSelect({ kind: 'gnb', gnb: g })}>▲ {g.name}<span className="muted"> {g.dus.length} DU</span></button>
          {g.dus.flatMap((d) => d.cells).map((c) => (
            <button key={c.cell_uuid} className={isSel('cell', c.cell_uuid) ? 'row sub sel' : 'row sub'} onClick={() => onSelect({ kind: 'cell', cell: c, gnb: g })}>◉ {c.name} <span className="muted">pci {c.pci}{c.position ? ' · DAS' : ''}{c.ru?.antenna_preset ? ` · ${c.ru.antenna_preset.rows}×${c.ru.antenna_preset.cols}` : ''}</span></button>))}
        </div>))}
      {tree.buildings.length > 0 && <div className="node"><div className="row head">建築</div>{tree.buildings.map((b) => <button key={b.building_uuid} className={isSel('building', b.building_uuid) ? 'row sub sel' : 'row sub'} onClick={() => onSelect({ kind: 'building', building: b })}>▦ {b.name} <span className="muted">{b.source}</span></button>)}</div>}
      <div className="node"><div className="row head">UE</div>
        {tree.ues.map((u) => <button key={u.ue_uuid} className={isSel('ue', u.ue_uuid) ? 'row sub sel' : 'row sub'} onClick={() => onSelect({ kind: 'ue', ue: u })}>● {u.name} <span className="muted">{u.waypoints.length} wp</span></button>)}</div>
    </div>
  );
}
