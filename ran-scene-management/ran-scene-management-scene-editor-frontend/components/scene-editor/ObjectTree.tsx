'use client';
import type { Selection } from '@/hooks/feature/useSceneEditorPage';
import type { SceneTree } from '@/types/registry';

export function ObjectTree({ tree, selection, onSelect, onAddCell }: { tree: SceneTree; selection: Selection; onSelect: (s: Selection) => void; onAddCell: (gnbUuid: string) => void }) {
  const isSel = (k: string, id: string) => (selection?.kind === 'gnb' && k === 'gnb' && selection.gnb.gnb_uuid === id) || (selection?.kind === 'cell' && k === 'cell' && selection.cell.cell_uuid === id) || (selection?.kind === 'ue' && k === 'ue' && selection.ue.ue_uuid === id);
  return (
    <div className="tree">
      <h3>{tree.scene.name}</h3>
      <p className="muted">{tree.gnbs.length} gNB · {tree.gnbs.reduce((n, g) => n + g.dus.reduce((m, d) => m + d.cells.length, 0), 0)} cell · {tree.ues.length} UE · {tree.buildings.length} 建築</p>
      {tree.gnbs.map((g) => (
        <div key={g.gnb_uuid} className="node">
          <button className={isSel('gnb', g.gnb_uuid) ? 'row sel' : 'row'} onClick={() => onSelect({ kind: 'gnb', gnb: g })}>▣ {g.name}</button>
          <button className="mini" onClick={() => onAddCell(g.gnb_uuid)} title="加一個共站 cell">+ cell</button>
          {g.dus.flatMap((d) => d.cells).map((c) => (
            <button key={c.cell_uuid} className={isSel('cell', c.cell_uuid) ? 'row sub sel' : 'row sub'} onClick={() => onSelect({ kind: 'cell', cell: c, gnb: g })}>
              ◉ {c.name} <span className="muted">pci {c.pci}{c.position ? ' · DAS' : ''}</span>
            </button>
          ))}
        </div>
      ))}
      <div className="node">
        <div className="row head">UE</div>
        {tree.ues.map((u) => (
          <button key={u.ue_uuid} className={isSel('ue', u.ue_uuid) ? 'row sub sel' : 'row sub'} onClick={() => onSelect({ kind: 'ue', ue: u })}>● {u.name} <span className="muted">{u.waypoints.length} wp</span></button>
        ))}
      </div>
    </div>
  );
}
