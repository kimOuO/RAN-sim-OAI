'use client';
import { useMemo } from 'react';
import { SceneCanvas } from '@/components/scene-canvas/SceneCanvas';
import { CheckList } from '@/components/scene-editor/CheckList';
import { EditorLayout } from '@/components/scene-editor/EditorLayout';
import { ObjectTree } from '@/components/scene-editor/ObjectTree';
import { Palette } from '@/components/scene-editor/Palette';
import { PreviewBar } from '@/components/scene-editor/PreviewBar';
import { PropertyPanel } from '@/components/scene-editor/PropertyPanel';
import { StepGate } from '@/components/scene-editor/StepGate';
import { UeGeneratorPanel } from '@/components/scene-editor/UeGeneratorPanel';
import { UeTrafficPanel } from '@/components/scene-editor/UeTrafficPanel';
import { ueChecks } from '@/hooks/feature/sceneChecks';
import { pathDuration, sceneExtent } from '@/hooks/feature/sceneGeometry';
import { panelProps, useEditorStep } from '@/hooks/feature/useEditorStep';
import { useScenePreview } from '@/hooks/feature/useScenePreview';

/** 步驟 3:UE —— 隨機種子產生 / 手動放置、路徑播放預覽、每個 UE 的流量與在場時段 */
export default function UeStep() {
  const { id, p } = useEditorStep();
  // 產生範圍:先用建築 / gNB;太小(例如掃描模型場景只有一個 gNB 點)就把既有 UE 路徑也算進來,仍太小就以中心 ±20 m
  const extent = useMemo(() => { if (!p.tree) return { xMin: -50, xMax: 50, zMin: -50, zMax: 50 };
    let e = sceneExtent({ ...p.tree, ues: [] }); const small = (x: typeof e) => x.xMax - x.xMin < 2 || x.zMax - x.zMin < 2;
    if (small(e) && p.tree.ues.length) e = sceneExtent(p.tree);
    if (small(e)) { const cx = (e.xMin + e.xMax) / 2, cz = (e.zMin + e.zMax) / 2; e = { xMin: cx - 20, xMax: cx + 20, zMin: cz - 20, zMax: cz + 20 }; }
    const r = (v: number) => Math.round(v * 10) / 10;
    return { xMin: r(e.xMin), xMax: r(e.xMax), zMin: r(e.zMin), zMax: r(e.zMax) }; }, [p.tree]);
  const preview = useScenePreview(p.tree ? pathDuration(p.tree) : 0);
  return <StepGate p={p}>{(tree) => { const checks = ueChecks(tree); const sel = p.selection?.kind === 'ue' ? tree.ues.find((u) => u.ue_uuid === (p.selection as { ue: { ue_uuid: string } }).ue.ue_uuid) : undefined; return (
    <EditorLayout tree={tree} step="ue" saving={p.saving} message={p.message} progress={p.progress}
      next={{ href: `/scenes/${id}/launch`, label: '下一步:模擬與啟動', blocked: checks.find((c) => c.level === 'error')?.text }}
      left={<>
        <UeGeneratorPanel extent={extent} saving={p.saving} ueCount={tree.ues.length} onGenerate={p.generateUes} onClear={p.clearUes} />
        <Palette kinds={['ue']} placeKind={p.placeKind} onPick={p.setPlaceKind} />
        <ObjectTree tree={tree} selection={p.selection} onSelect={p.select} sections={['ue']} />
        <CheckList title="檢查" checks={checks} />
      </>}
      center={<>
        <SceneCanvas tree={tree} selection={p.selection} placing={p.placeKind != null} onSelect={p.select} onGroundClick={p.placeAt} onCellMoved={p.moveCell} onGnbMoved={p.moveGnb}
          previewT={preview.playing || preview.t > 0 ? preview.t : null} />
        <PreviewBar p={preview} />
      </>}
      right={<PropertyPanel {...panelProps(p, tree)} tabs={['props', 'antenna']} emptyHint="點 UE 設定天線高、5QI、流量與在場時段;下方播放列可預覽所有 UE 的移動。"
        extra={sel && <UeTrafficPanel ue={sel} saving={p.saving} onTraffic={p.setUeTraffic} onWindows={p.setUeWindows} />} />}
    />); }}</StepGate>;
}
