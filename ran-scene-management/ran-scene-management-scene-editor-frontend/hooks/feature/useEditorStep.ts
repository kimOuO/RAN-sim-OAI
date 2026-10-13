'use client';
import { useEffect } from 'react';
import { useParams } from 'next/navigation';
import { useSceneEditorPage } from '@/hooks/feature/useSceneEditorPage';

/** 步驟頁共用:讀場景 + Esc 取消放置模式 */
export function useEditorStep() {
  const { id } = useParams<{ id: string }>();
  const p = useSceneEditorPage(id);
  const { setPlaceKind } = p;
  useEffect(() => { const h = (e: KeyboardEvent) => { if (e.key === 'Escape') setPlaceKind(null); }; window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h); }, [setPlaceKind]);
  return { id, p };
}

type EditorPage = ReturnType<typeof useSceneEditorPage>;
/** 右側屬性面板需要的一大包 props(各步驟共用) */
export function panelProps(p: EditorPage, tree: NonNullable<EditorPage['tree']>) {
  return {
    selection: p.selection, presets: p.presets, templates: p.templates, gnbTemplates: p.gnbTemplates, materials: p.materials, scene: tree.scene, gnbs: tree.gnbs, onSceneAntenna: p.setSceneAntenna, onE2Block: p.setE2Block, onCategory: p.setCategory,
    onApplyGnbTemplate: p.applyGnbTemplate, onSaveGnbTemplate: p.saveGnbAsTemplate, onAntennaFields: p.applyAntennaFields, onSaveAntennaPreset: p.saveAntennaAsPreset,
    run: p.run, knobs: p.knobs, saving: p.saving, message: null,
    onCell: p.updateCellFields, onGnb: p.updateGnbFields, onDu: p.updateDuFields, onUe: p.updateUeFields, onBuilding: p.updateBuildingFields,
    onCellAntenna: p.setCellAntenna, onUeAntenna: p.setUeAntenna, onRun: p.updateRunFields, onKnob: p.setKnob, onRemoveKnob: p.removeKnob, onDelete: p.removeSelected,
  };
}
