'use client';
import { useState } from 'react';
import { useAsync } from '@/hooks/base/useAsync';
import { createAntennaPreset, createDuConfigTemplate, createMaterial, deleteAntennaPreset, deleteDuConfigTemplate, listAntennaPresets, listDuConfigTemplates, listMaterials, updateAntennaPreset, updateDuConfigTemplate, updateMaterial } from '@/services/api/presets';
import type { AntennaPreset, DuConfigTemplate, Material } from '@/types/registry';

export type NeTab = 'antenna' | 'du' | 'material';
/** 網路元件管理:三種可重用資源的 CRUD;表單值是字串,寫回時依欄位型別轉換 */
export function useNetworkElementsPage() {
  const antennas = useAsync(listAntennaPresets, []); const templates = useAsync(listDuConfigTemplates, []); const materials = useAsync(listMaterials, []);
  const [tab, setTab] = useState<NeTab>('antenna'); const [editing, setEditing] = useState<string | 'new' | null>(null);
  const [msg, setMsg] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const refetch = () => { antennas.refetch(); templates.refetch(); materials.refetch(); };
  async function run(label: string, fn: () => Promise<unknown>) { setBusy(true); setMsg(null); try { await fn(); setMsg(`${label} 完成`); setEditing(null); refetch(); } catch (e) { setMsg(`${label} 失敗:${e instanceof Error ? e.message : String(e)}`); } finally { setBusy(false); } }
  return {
    tab, setTab, editing, setEditing, msg, busy, antennas: antennas.data ?? [], templates: templates.data ?? [], materials: materials.data ?? [],
    saveAntenna: (uuid: string | null, body: Partial<AntennaPreset>) => run('天線陣列', () => uuid ? updateAntennaPreset(uuid, body) : createAntennaPreset(body)),
    removeAntenna: (uuid: string) => run('刪除天線陣列', () => deleteAntennaPreset(uuid)),
    saveTemplate: (uuid: string | null, body: Partial<DuConfigTemplate>) => run('DU 設定模板', () => uuid ? updateDuConfigTemplate(uuid, body) : createDuConfigTemplate(body)),
    removeTemplate: (uuid: string) => run('刪除模板', () => deleteDuConfigTemplate(uuid)),
    saveMaterial: (uuid: string | null, body: Partial<Material>) => run('材質', () => uuid ? updateMaterial(uuid, body) : createMaterial(body)),
  };
}
