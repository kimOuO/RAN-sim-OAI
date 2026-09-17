'use client';
import { useRouter } from 'next/navigation';
import { SceneCanvas } from '@/components/scene-canvas/SceneCanvas';
import { CheckList } from '@/components/scene-editor/CheckList';
import { EditorLayout } from '@/components/scene-editor/EditorLayout';
import { MapFetchPanel } from '@/components/scene-editor/MapFetchPanel';
import { ObjectTree } from '@/components/scene-editor/ObjectTree';
import { Palette } from '@/components/scene-editor/Palette';
import { PropertyPanel } from '@/components/scene-editor/PropertyPanel';
import { SceneInfoPanel } from '@/components/scene-editor/SceneInfoPanel';
import { StepGate } from '@/components/scene-editor/StepGate';
import { environmentChecks } from '@/hooks/feature/sceneChecks';
import { panelProps, useEditorStep } from '@/hooks/feature/useEditorStep';

/** 步驟 1:找場景 —— 地圖(OSM)/ 匯入(掃描模型)/ 自己拉建築盒;以物件為單位設定材質 */
export default function EnvironmentStep() {
  const { id, p } = useEditorStep(); const router = useRouter();
  return <StepGate p={p}>{(tree) => (
    <EditorLayout tree={tree} step="environment" saving={p.saving} message={p.message} next={{ href: `/scenes/${id}/network`, label: '下一步:網路元件' }}
      left={<>
        <SceneInfoPanel tree={tree} saving={p.saving} sources={p.geometrySources} onSave={p.updateSceneInfo} onDuplicate={p.duplicate} onOpen={(sid) => router.push(`/scenes/${sid}/environment`)} />
        <Palette kinds={['building']} placeKind={p.placeKind} onPick={p.setPlaceKind} />
        <MapFetchPanel query={p.osm.query} results={p.osm.results} picked={p.osm.picked} busy={p.osm.busy} onQuery={p.setOsmQuery} onSearch={p.osmSearch} onPick={p.setOsmPicked} onFetch={p.osmFetch} />
        <ObjectTree tree={tree} selection={p.selection} onSelect={p.select} sections={['building']} />
        <CheckList title="檢查" checks={environmentChecks(tree)} />
      </>}
      center={<SceneCanvas tree={tree} selection={p.selection} placing={p.placeKind != null} onSelect={p.select} onGroundClick={p.placeAt} onCellMoved={p.moveCell} onGnbMoved={p.moveGnb} />}
      right={<PropertyPanel {...panelProps(p, tree)} tabs={['props']} emptyHint="點建築(畫布或左側清單)調整位置、尺寸與材質;gNB / UE 在後面的步驟設定。" />}
    />)}</StepGate>;
}

