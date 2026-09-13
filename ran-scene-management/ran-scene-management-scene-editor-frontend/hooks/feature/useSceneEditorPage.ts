'use client';
import { useCallback, useMemo, useState } from 'react';
import { useAsync } from '@/hooks/base/useAsync';
import { attachOsmToScene, generateOsmMap, geocodeLandmark, listOsmMaps } from '@/services/api/geometry';
import { createBuilding, createCell, createDu, createGnb, createRu, createUe, createUeWaypoint, deleteBuilding, deleteCell, deleteGnb, deleteUe, updateBuilding, updateCell, updateDu, updateGnb, updateRu, updateUe } from '@/services/api/networkElements';
import { listAntennaPresets, listDuConfigTemplates, listMaterials } from '@/services/api/presets';
import { createRunKnob, createSceneRun, deleteRunKnob, listRunKnobs, listSceneRuns, updateRunKnob, updateSceneRun } from '@/services/api/runs';
import { getSceneTree } from '@/services/api/scenes';
import type { Building, Cell, Du, Gnb, SceneRun, Ue } from '@/types/registry';
import type { GeocodeResult } from '@/types/geometry';

export type Selection = { kind: 'gnb'; gnb: Gnb } | { kind: 'cell'; cell: Cell; gnb: Gnb } | { kind: 'ue'; ue: Ue } | { kind: 'building'; building: Building } | null;
/** 元件庫的「放置模式」:選了元件後,下一次點地面就建立 */
export type PlaceKind = 'gnb' | 'cell' | 'ue' | 'building' | null;

/** 編輯器頁的全部狀態:樹、選取、放置、屬性/天線/RAN 參數寫回、OSM 拉地圖。元件只負責畫。 */
export function useSceneEditorPage(sceneUuid: string) {
  const tree = useAsync(() => getSceneTree(sceneUuid), [sceneUuid]);
  const presets = useAsync(listAntennaPresets, []); const templates = useAsync(listDuConfigTemplates, []); const materials = useAsync(listMaterials, []);
  const runs = useAsync(() => listSceneRuns(sceneUuid), [sceneUuid]);
  const run: SceneRun | null = useMemo(() => (runs.data ?? [])[0] ?? null, [runs.data]);
  const knobs = useAsync(() => (run ? listRunKnobs(run.scene_run_uuid) : Promise.resolve([])), [run?.scene_run_uuid]);
  const [selection, setSelection] = useState<Selection>(null);
  const [placeKind, setPlaceKind] = useState<PlaceKind>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [osm, setOsm] = useState<{ query: string; results: GeocodeResult[]; picked: GeocodeResult | null; busy: string | null }>({ query: '', results: [], picked: null, busy: null });

  const withSave = useCallback(async (label: string, fn: () => Promise<unknown>) => {
    setSaving(true); setMessage(null);
    try { await fn(); setMessage(`${label} 已儲存`); tree.refetch(); }
    catch (e) { setMessage(`${label} 失敗:${e instanceof Error ? e.message : String(e)}`); }
    finally { setSaving(false); }
  }, [tree]);
  const gnbs = tree.data?.gnbs ?? [];
  const selGnb = selection?.kind === 'gnb' ? selection.gnb : selection?.kind === 'cell' ? selection.gnb : null;

  /** 點地面:依放置模式建立物件(gNB 自帶 DU/cell/RU;cell 要先選 gNB;UE 建一個 waypoint;建築是 10×6×10 盒) */
  const placeAt = (pos: [number, number, number]) => {
    const [x, , z] = pos; const n = (k: string) => `${k}${(k === 'gnb' ? gnbs.length : k === 'ue' ? (tree.data?.ues.length ?? 0) : (tree.data?.buildings.length ?? 0)) + 1}`;
    if (placeKind === 'gnb') void withSave(`gNB ${n('gnb')}`, async () => { const g = await createGnb({ f_scene_uuid: sceneUuid, name: n('gnb'), position: [x, 0, z] }); const d = await createDu({ f_gnb_uuid: g.gnb_uuid, name: `${g.name}_du0` }); const c = await createCell({ f_du_uuid: d.du_uuid, name: `${g.name}_c0`, pci: gnbs.length }); await createRu({ f_cell_uuid: c.cell_uuid, name: `${g.name}_c0_ru` }); });
    else if (placeKind === 'cell') { if (!selGnb) { setMessage('先選一個 gNB,再放 cell(DAS 拉遠)'); return; } const du = selGnb.dus[0]; const k = du.cells.length; void withSave(`cell ${selGnb.name}_c${k}`, async () => { const c = await createCell({ f_du_uuid: du.du_uuid, name: `${selGnb.name}_c${k}`, pci: k, position: [x, 0, z], azimuth_deg: (k * 120) % 360 }); await createRu({ f_cell_uuid: c.cell_uuid, name: `${c.name}_ru` }); }); }
    else if (placeKind === 'ue') void withSave(`UE ${n('ue')}`, async () => { const u = await createUe({ f_scene_uuid: sceneUuid, name: n('ue'), antenna_height_m: 1.5, qos_5qi: 9, color: [0.8, 0.8, 0.8] }); await createUeWaypoint({ f_ue_uuid: u.ue_uuid, ord: 0, t_sec: 0, x, y: 1.5, z }); });
    else if (placeKind === 'building') void withSave(`建築 ${n('b')}`, () => createBuilding({ f_scene_uuid: sceneUuid, name: n('b'), source: 'manual_box', geometry_ref: '', position: [x, 0, z], size: [10, 6, 10], rotation: [0, 0, 0], scale: [1, 1, 1] }));
    setPlaceKind(null);
  };

  /** OSM:地標 → 候選 → 抓地圖 → 掛到場景成 building(source=osm) */
  const osmSearch = async () => { setOsm((o) => ({ ...o, busy: 'geocode' })); try { const r = await geocodeLandmark(osm.query); setOsm((o) => ({ ...o, results: r, picked: r[0] ?? null, busy: null })); } catch (e) { setMessage(`地標搜尋失敗:${e instanceof Error ? e.message : e}`); setOsm((o) => ({ ...o, busy: null })); } };
  const osmFetch = async () => {
    const g = osm.picked; if (!g) return; setOsm((o) => ({ ...o, busy: 'generate' }));
    const name = `${(tree.data?.scene.name ?? 'scene').replace(/[^A-Za-z0-9_]/g, '_')}_${g.name.replace(/[^A-Za-z0-9_]/g, '_').slice(0, 24)}`;
    await withSave(`地圖 ${g.name}`, async () => {
      const existing = (await listOsmMaps()).find((a) => a.name === name && a.status === 'ready');
      const asset = existing ?? await generateOsmMap({ name, label: g.display_name, ...g.bbox });
      await attachOsmToScene(asset.osm_map_asset_uuid, sceneUuid);
    });
    setOsm((o) => ({ ...o, busy: null }));
  };

  return {
    tree: tree.data, status: tree.status, error: tree.error, presets: presets.data ?? [], templates: templates.data ?? [], materials: materials.data ?? [],
    run, knobs: knobs.data ?? [], selection, select: (s: Selection) => { setSelection(s); }, saving, message, placeKind, setPlaceKind, placeAt,
    osm, setOsmQuery: (q: string) => setOsm((o) => ({ ...o, query: q })), setOsmPicked: (g: GeocodeResult) => setOsm((o) => ({ ...o, picked: g })), osmSearch, osmFetch,
    moveCell: (c: Cell, pos: [number, number, number]) => withSave(`cell ${c.name} 位置`, () => updateCell(c.cell_uuid, { position: pos })),
    moveGnb: (g: Gnb, pos: [number, number, number]) => withSave(`gNB ${g.name} 位置`, () => updateGnb(g.gnb_uuid, { position: pos })),
    updateCellFields: (c: Cell, f: Partial<Cell>) => withSave(`cell ${c.name}`, () => updateCell(c.cell_uuid, f)),
    updateGnbFields: (g: Gnb, f: Partial<Gnb>) => withSave(`gNB ${g.name}`, () => updateGnb(g.gnb_uuid, f)),
    updateDuFields: (d: Du, f: Partial<Du>) => withSave(`DU ${d.name}`, () => updateDu(d.du_uuid, f)),
    updateUeFields: (u: Ue, f: Partial<Ue>) => withSave(`UE ${u.name}`, () => updateUe(u.ue_uuid, f)),
    updateBuildingFields: (b: Building, f: Partial<Building>) => withSave(`建築 ${b.name}`, () => updateBuilding(b.building_uuid, f)),
    removeSelected: () => { const s = selection; if (!s) return; setSelection(null);
      if (s.kind === 'gnb') void withSave(`刪除 gNB ${s.gnb.name}`, () => deleteGnb(s.gnb.gnb_uuid)); else if (s.kind === 'cell') void withSave(`刪除 cell ${s.cell.name}`, () => deleteCell(s.cell.cell_uuid));
      else if (s.kind === 'ue') void withSave(`刪除 UE ${s.ue.name}`, () => deleteUe(s.ue.ue_uuid)); else void withSave(`刪除建築 ${s.building.name}`, () => deleteBuilding(s.building.building_uuid)); },
    setCellAntenna: (c: Cell, uuid: string | null, override?: unknown) => withSave(`cell ${c.name} 天線`, async () => c.ru ? updateRu(c.ru.ru_uuid, { f_antenna_preset_uuid: uuid, ...(override !== undefined ? { antenna_override: override } : {}) }) : createRu({ f_cell_uuid: c.cell_uuid, name: `${c.name}_ru`, f_antenna_preset_uuid: uuid })),
    setUeAntenna: (u: Ue, uuid: string | null) => withSave(`UE ${u.name} 天線`, () => updateUe(u.ue_uuid, { f_antenna_preset_uuid: uuid })),
    /** run 層:沒有 run 就先建 draft;knob 以 key 唯一 */
    updateRunFields: (f: Partial<SceneRun>) => withSave('run 設定', async () => { if (run) await updateSceneRun(run.scene_run_uuid, f); else await createSceneRun({ f_scene_uuid: sceneUuid, ...f }); runs.refetch(); }),
    setKnob: (key: string, value: string) => withSave(`knob ${key}`, async () => {
      let r = run; if (!r) { r = await createSceneRun({ f_scene_uuid: sceneUuid }); runs.refetch(); }
      const ex = (knobs.data ?? []).find((k) => k.key === key); let v: unknown = value; try { v = JSON.parse(value); } catch { /* 純字串 */ }
      if (ex) await updateRunKnob(ex.run_knob_uuid, v); else await createRunKnob({ f_scene_run_uuid: r.scene_run_uuid, key, value: v }); knobs.refetch(); }),
    removeKnob: (uuid: string) => withSave('knob 刪除', async () => { await deleteRunKnob(uuid); knobs.refetch(); }),
  };
}
