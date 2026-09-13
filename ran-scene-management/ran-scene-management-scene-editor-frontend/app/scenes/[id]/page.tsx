'use client';
import Link from 'next/link';
import { useEffect } from 'react';
import { useParams } from 'next/navigation';
import { SceneCanvas } from '@/components/scene-canvas/SceneCanvas';
import { MapFetchPanel } from '@/components/scene-editor/MapFetchPanel';
import { ObjectTree } from '@/components/scene-editor/ObjectTree';
import { Palette } from '@/components/scene-editor/Palette';
import { PropertyPanel } from '@/components/scene-editor/PropertyPanel';
import { useSceneEditorPage } from '@/hooks/feature/useSceneEditorPage';

export default function SceneEditorPage() {
  const { id } = useParams<{ id: string }>();
  const p = useSceneEditorPage(id);
  useEffect(() => { const h = (e: KeyboardEvent) => { if (e.key === 'Escape') p.setPlaceKind(null); }; window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h); }, [p]);
  if (p.status === 'loading' && !p.tree) return <p className="muted shell page">載入場景…</p>;
  if (p.error) return <p className="err shell page">{p.error.message}</p>;
  if (!p.tree) return null;
  return (
    <section className="editor">
      <div className="editor-bar"><Link href="/scenes" className="muted">場景</Link><span className="muted">/</span><b>{p.tree.scene.name}</b>{p.tree.scene.legacy_scenario_id && <span className="muted small">劇本 {p.tree.scene.legacy_scenario_id}</span>}
        <span className="sp" />{p.saving && <span className="muted small">儲存中…</span>}{p.message && <span className="msg small">{p.message}</span>}</div>
      <div className="editor-body">
        <div className="left">
          <Palette placeKind={p.placeKind} onPick={p.setPlaceKind} />
          <MapFetchPanel query={p.osm.query} results={p.osm.results} picked={p.osm.picked} busy={p.osm.busy} onQuery={p.setOsmQuery} onSearch={p.osmSearch} onPick={p.setOsmPicked} onFetch={p.osmFetch} />
          <ObjectTree tree={p.tree} selection={p.selection} onSelect={p.select} />
        </div>
        <div className="center"><SceneCanvas tree={p.tree} selection={p.selection} placing={p.placeKind != null} onSelect={p.select} onGroundClick={p.placeAt} onCellMoved={p.moveCell} onGnbMoved={p.moveGnb} /></div>
        <PropertyPanel selection={p.selection} presets={p.presets} templates={p.templates} gnbTemplates={p.gnbTemplates} materials={p.materials}
          onApplyGnbTemplate={p.applyGnbTemplate} onSaveGnbTemplate={p.saveGnbAsTemplate} onAntennaFields={p.applyAntennaFields} onSaveAntennaPreset={p.saveAntennaAsPreset} run={p.run} knobs={p.knobs} saving={p.saving} message={null}
          onCell={p.updateCellFields} onGnb={p.updateGnbFields} onDu={p.updateDuFields} onUe={p.updateUeFields} onBuilding={p.updateBuildingFields}
          onCellAntenna={p.setCellAntenna} onUeAntenna={p.setUeAntenna} onRun={p.updateRunFields} onKnob={p.setKnob} onRemoveKnob={p.removeKnob} onDelete={p.removeSelected} />
      </div>
    </section>
  );
}
