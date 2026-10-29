'use client';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { SceneCanvas } from '@/components/scene-canvas/SceneCanvas';
import { CheckList } from '@/components/scene-editor/CheckList';
import { EditorLayout } from '@/components/scene-editor/EditorLayout';
import { BuildingMaterialPanel } from '@/components/scene-editor/map/BuildingMaterialPanel';
import { MapAreaPanel } from '@/components/scene-editor/map/MapAreaPanel';
import { ObjectTree } from '@/components/scene-editor/ObjectTree';
import { GeometryObjectList } from '@/components/scene-editor/GeometryObjectList';
import { Palette } from '@/components/scene-editor/Palette';
import { PropertyPanel } from '@/components/scene-editor/PropertyPanel';
import { ScanUploadPanel } from '@/components/scene-editor/ScanUploadPanel';
import { SceneInfoPanel } from '@/components/scene-editor/SceneInfoPanel';
import { SourcePicker } from '@/components/scene-editor/SourcePicker';
import { StepGate } from '@/components/scene-editor/StepGate';
import { environmentChecks } from '@/hooks/feature/sceneChecks';
import { useMapBuilder } from '@/hooks/feature/useMapBuilder';
import { panelProps, useEditorStep } from '@/hooks/feature/useEditorStep';
import type { SceneTree } from '@/types/registry';

// Leaflet 碰到 window,只能在瀏覽器載入
const MapCanvas = dynamic(() => import('@/components/scene-editor/map/MapCanvas'), { ssr: false, loading: () => <div className="muted center-hint">地圖載入中…</div> });

type Layer = 'source' | 'map' | 'scan' | '3d';
const hasGeometry = (tree: SceneTree) => !!(tree.scene.geometry_source as { type?: string } | null)?.type || tree.buildings.length > 0;

/** 步驟 1:第一層選場景來源(地圖框選 / 上傳掃描檔),第二層在 3D 檢視場景與調整建築 */
export default function EnvironmentStep() {
  const { id, p } = useEditorStep();
  return <StepGate p={p}>{(tree) => <Environment id={id} p={p} tree={tree} />}</StepGate>;
}

function Environment({ id, p, tree }: { id: string; p: ReturnType<typeof useEditorStep>['p']; tree: SceneTree }) {
  const router = useRouter();
  const [layer, setLayer] = useState<Layer>(hasGeometry(tree) ? '3d' : 'source');
  const toThreeD = () => { p.reloadTree(); setLayer('3d'); };
  const m = useMapBuilder(id, toThreeD);
  const next = { href: `/scenes/${id}/network`, label: '下一步:網路元件', blocked: hasGeometry(tree) ? null : '還沒有場景幾何' };
  const base = { tree, step: 'environment' as const, saving: p.saving, message: p.message, next };

  if (layer === 'source' || layer === 'scan') {
    return <EditorLayout {...base}
      left={<SceneInfoPanel tree={tree} saving={p.saving} sources={p.geometrySources} onSave={p.updateSceneInfo} onDuplicate={p.duplicate} onOpen={(sid) => router.push(`/scenes/${sid}/environment`)} />}
      center={layer === 'source'
        ? <SourcePicker hasGeometry={hasGeometry(tree)} onPick={setLayer} onCancel={hasGeometry(tree) ? () => setLayer('3d') : null} />
        : <ScanUploadPanel sceneUuid={id} defaultName={tree.scene.name} onDone={toThreeD} onBack={() => setLayer('source')} />}
      right={<aside className="panel"><p className="muted small">先選場景來源;建立後進入 3D,再放網路元件與 UE。</p></aside>} />;
  }
  if (layer === 'map') {
    return <EditorLayout {...base}
      left={<MapAreaPanel m={m} onBack={() => setLayer('source')} />}
      center={<MapCanvas polygon={m.polygon} drawing={m.drawing} buildings={m.buildings} selected={m.selected} flyTo={m.flyTo}
        onPolygon={m.setPolygon} onDrawPoint={m.addDrawPoint} onFinishDraw={m.finishDraw} onBuilding={m.toggle} />}
      right={<BuildingMaterialPanel m={m} materials={p.materials} defaultName={tree.scene.name} />} />;
  }
  return <EditorLayout {...base}
    left={<>
      <SceneInfoPanel tree={tree} saving={p.saving} sources={p.geometrySources} onSave={p.updateSceneInfo} onDuplicate={p.duplicate} onOpen={(sid) => router.push(`/scenes/${sid}/environment`)} />
      <button className="wide" onClick={() => setLayer('source')}>更換場景來源(地圖 / 掃描檔)</button>
      <Palette kinds={['building']} placeKind={p.placeKind} onPick={p.setPlaceKind} />
      <ObjectTree tree={tree} selection={p.selection} onSelect={p.select} sections={['building']} />
      <GeometryObjectList meshes={p.meshes} selectedId={p.selection?.kind === 'mesh' ? p.selection.mesh.shape_id : null} onSelect={(mesh) => p.select({ kind: 'mesh', mesh })} />
      <CheckList title="檢查" checks={environmentChecks(tree)} />
    </>}
    center={<SceneCanvas tree={tree} selection={p.selection} placing={p.placeKind != null} meshes={p.meshes} onMeshSelect={(mesh) => p.select({ kind: 'mesh', mesh })} onSelect={p.select} onGroundClick={p.placeAt} onCellMoved={p.moveCell} onGnbMoved={p.moveGnb} onUeMoved={p.moveUe} />}
    right={<PropertyPanel {...panelProps(p, tree)} tabs={['props']} emptyHint="點建築(畫布或左側清單)調整位置、尺寸與材質;gNB / UE 在後面的步驟設定。" />}
  />;
}
