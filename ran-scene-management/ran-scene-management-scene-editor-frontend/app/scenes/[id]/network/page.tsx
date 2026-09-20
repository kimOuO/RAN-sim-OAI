'use client';
import { SceneCanvas } from '@/components/scene-canvas/SceneCanvas';
import { CoverageLayer } from '@/components/scene-canvas/CoverageLayer';
import { CheckList } from '@/components/scene-editor/CheckList';
import { CoveragePanel } from '@/components/scene-editor/CoveragePanel';
import { EditorLayout } from '@/components/scene-editor/EditorLayout';
import { GnbTemplatePicker } from '@/components/scene-editor/GnbTemplatePicker';
import { ObjectTree } from '@/components/scene-editor/ObjectTree';
import { Palette } from '@/components/scene-editor/Palette';
import { PropertyPanel } from '@/components/scene-editor/PropertyPanel';
import { StepGate } from '@/components/scene-editor/StepGate';
import { networkChecks } from '@/hooks/feature/sceneChecks';
import { useCoverage } from '@/hooks/feature/useCoverage';
import { panelProps, useEditorStep } from '@/hooks/feature/useEditorStep';

/** 步驟 2:網路元件 —— gNB / cell(含拉遠)、天線、A3、DU 模板;可把現場設定存成模板 */
export default function NetworkStep() {
  const { id, p } = useEditorStep();
  const cov = useCoverage(id);
  return <StepGate p={p}>{(tree) => { const checks = networkChecks(tree); return (
    <EditorLayout tree={tree} step="network" saving={p.saving} message={p.message}
      next={{ href: `/scenes/${id}/ue`, label: '下一步:UE', blocked: checks.find((c) => c.level === 'error')?.text }}
      left={<>
        <GnbTemplatePicker templates={p.gnbTemplates} value={p.placeTemplateUuid} onChange={p.setPlaceTemplateUuid} />
        <Palette kinds={['gnb', 'cell']} placeKind={p.placeKind} onPick={p.setPlaceKind}
          blocked={{ cell: p.selGnb ? undefined : '先在畫布上選一個 gNB(拉遠單元要掛在它的 DU 底下)' }} />
        <ObjectTree tree={tree} selection={p.selection} onSelect={p.select} sections={['gnb']} />
        <CheckList title="檢查" checks={checks} />
        <CoveragePanel c={cov} />
      </>}
      center={<SceneCanvas tree={tree} selection={p.selection} placing={p.placeKind != null} onSelect={p.select} onGroundClick={p.placeAt} onCellMoved={p.moveCell} onGnbMoved={p.moveGnb} onUeMoved={p.moveUe}
        overlay={cov.result && cov.show ? <CoverageLayer result={cov.result} mode={cov.mode} opacity={cov.opacity} /> : null} />}
      right={<PropertyPanel {...panelProps(p, tree)} showRun={false} emptyHint="點 gNB 或 cell 設定參數;沒選物件時「天線」分頁可設整個場景的 gNB / UE 陣列。" />}
    />); }}</StepGate>;
}
