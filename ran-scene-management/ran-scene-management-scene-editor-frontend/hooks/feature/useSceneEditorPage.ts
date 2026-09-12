'use client';
import { useCallback, useMemo, useState } from 'react';
import { useAsync } from '@/hooks/base/useAsync';
import { listAntennaPresets } from '@/services/api/presets';
import { createCell, createDu, createGnb, createRu, updateCell, updateGnb, updateRu } from '@/services/api/networkElements';
import { getSceneTree } from '@/services/api/scenes';
import type { Cell, Gnb, Ue } from '@/types/registry';

export type Selection = { kind: 'gnb'; gnb: Gnb } | { kind: 'cell'; cell: Cell; gnb: Gnb } | { kind: 'ue'; ue: Ue } | { kind: 'building'; index: number } | null;

/** 編輯器頁的全部狀態:樹、選取、拖曳後的位置寫回、屬性更新。元件只負責畫。 */
export function useSceneEditorPage(sceneUuid: string) {
  const tree = useAsync(() => getSceneTree(sceneUuid), [sceneUuid]);
  const presets = useAsync(listAntennaPresets, []);
  const [selection, setSelection] = useState<Selection>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const cellsFlat = useMemo(() => (tree.data?.gnbs ?? []).flatMap((g) => g.dus.flatMap((d) => d.cells.map((c) => ({ cell: c, gnb: g })))), [tree.data]);

  const withSave = useCallback(async (label: string, fn: () => Promise<unknown>) => {
    setSaving(true); setMessage(null);
    try { await fn(); setMessage(`${label} 已儲存`); tree.refetch(); }
    catch (e) { setMessage(`${label} 失敗:${e instanceof Error ? e.message : String(e)}`); }
    finally { setSaving(false); }
  }, [tree]);

  return {
    tree: tree.data, status: tree.status, error: tree.error, presets: presets.data ?? [],
    selection, select: setSelection, saving, message, cellsFlat,
    /** cell 在畫布上被拖到新位置(公尺,Y-up)。拖離 gNB = DAS。 */
    moveCell: (c: Cell, pos: [number, number, number]) => withSave(`cell ${c.name} 位置`, () => updateCell(c.cell_uuid, { position: pos })),
    moveGnb: (g: Gnb, pos: [number, number, number]) => withSave(`gNB ${g.name} 位置`, () => updateGnb(g.gnb_uuid, { position: pos })),
    updateCellFields: (c: Cell, fields: Partial<Cell>) => withSave(`cell ${c.name}`, () => updateCell(c.cell_uuid, fields)),
    updateGnbFields: (g: Gnb, fields: Partial<Gnb>) => withSave(`gNB ${g.name}`, () => updateGnb(g.gnb_uuid, fields)),
    setCellAntenna: (c: Cell, antennaPresetUuid: string | null) =>
      withSave(`cell ${c.name} 天線`, async () => {
        if (c.ru) return updateRu(c.ru.ru_uuid, { f_antenna_preset_uuid: antennaPresetUuid });
        return createRu({ f_cell_uuid: c.cell_uuid, name: `${c.name}_ru`, f_antenna_preset_uuid: antennaPresetUuid });
      }),
    /** 拉一個 gNB:自動建 1 DU + 1 cell + 1 ru 在同位置(§3 畫布物件模型) */
    addGnb: (name: string, pos: [number, number, number]) =>
      withSave(`gNB ${name}`, async () => {
        const g = await createGnb({ f_scene_uuid: sceneUuid, name, position: pos });
        const d = await createDu({ f_gnb_uuid: g.gnb_uuid, name: `${name}_du0` });
        const c = await createCell({ f_du_uuid: d.du_uuid, name: `${name}_c0`, pci: 0 });
        await createRu({ f_cell_uuid: c.cell_uuid, name: `${name}_c0_ru` });
      }),
    /** 在既有 gNB 加一個共站 cell(位置留 null = 沿用 gNB) */
    addCell: (g: Gnb) =>
      withSave(`gNB ${g.name} 加 cell`, async () => {
        const du = g.dus[0];
        const n = du.cells.length;
        const c = await createCell({ f_du_uuid: du.du_uuid, name: `${g.name}_c${n}`, pci: n, azimuth_deg: (n * 120) % 360 });
        await createRu({ f_cell_uuid: c.cell_uuid, name: `${g.name}_c${n}_ru` });
      }),
  };
}
