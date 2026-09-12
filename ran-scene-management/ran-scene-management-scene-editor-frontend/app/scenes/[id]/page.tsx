'use client';
import { useParams } from 'next/navigation';
import { SceneCanvas } from '@/components/scene-canvas/SceneCanvas';
import { ObjectTree } from '@/components/scene-editor/ObjectTree';
import { PropertyPanel } from '@/components/scene-editor/PropertyPanel';
import { useSceneEditorPage } from '@/hooks/feature/useSceneEditorPage';

export default function SceneEditorPage() {
  const { id } = useParams<{ id: string }>();
  const p = useSceneEditorPage(id);
  if (p.status === 'loading' && !p.tree) return <p className="muted page">載入場景…</p>;
  if (p.error) return <p className="err page">{p.error.message}</p>;
  if (!p.tree) return null;
  return (
    <section className="editor">
      <div className="left">
        <ObjectTree tree={p.tree} selection={p.selection} onSelect={p.select} onAddCell={(uuid) => { const g = p.tree!.gnbs.find((x) => x.gnb_uuid === uuid); if (g) p.addCell(g); }} />
        <button className="wide" onClick={() => { const n = prompt('gNB 名稱', `gnb${p.tree!.gnbs.length + 1}`); if (n) p.addGnb(n, [0, 0, 0]); }}>+ gNB(自動帶 1 DU / 1 cell / 1 RU)</button>
      </div>
      <div className="center">
        <SceneCanvas tree={p.tree} selection={p.selection} onSelect={p.select} onCellMoved={p.moveCell} onGnbMoved={p.moveGnb} />
      </div>
      <PropertyPanel selection={p.selection} presets={p.presets} saving={p.saving} message={p.message} onCell={p.updateCellFields} onGnb={p.updateGnbFields} onAntenna={p.setCellAntenna} />
    </section>
  );
}
