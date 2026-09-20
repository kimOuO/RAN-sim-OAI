'use client';
import { SceneCanvas } from '@/components/scene-canvas/SceneCanvas';
import { EditorLayout } from '@/components/scene-editor/EditorLayout';
import { LaunchPanel } from '@/components/scene-editor/LaunchPanel';
import { PropertyPanel } from '@/components/scene-editor/PropertyPanel';
import { StepGate } from '@/components/scene-editor/StepGate';
import { launchChecks } from '@/hooks/feature/sceneChecks';
import { panelProps, useEditorStep } from '@/hooks/feature/useEditorStep';

/** 步驟 4:模擬設定(模式 / 倍速 / sim_dt / 長度 / knobs)→ Precompute → 啟動 */
export default function LaunchStep() {
  const { p } = useEditorStep();
  return <StepGate p={p}>{(tree) => (
    <EditorLayout tree={tree} step="launch" saving={p.saving} message={p.message}
      left={<LaunchPanel run={p.run} checks={launchChecks(tree, p.run, p.allRuns, p.knobs)} precomp={p.precomp} saving={p.saving}
        onPrecompute={p.precompute} onStopPrecompute={p.stopPrecompute} onStart={p.start} onStop={p.stop} onRefresh={p.refreshRuns} />}
      center={<SceneCanvas tree={tree} selection={null} placing={false} onSelect={() => undefined} onGroundClick={() => undefined} onCellMoved={() => undefined} onGnbMoved={() => undefined} />}
      right={<PropertyPanel {...panelProps(p, tree)} selection={null} tabs={['ran']} />}
    />)}</StepGate>;
}
