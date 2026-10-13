'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { UeGenParams } from '@/config';
import { planUes, walkableFromHeightMap } from '@/hooks/feature/ueGenerator';
import { useAsync } from '@/hooks/base/useAsync';
import { GNB_ABOVE_SURFACE_M, UE_ABOVE_SURFACE_M } from '@/components/scene-canvas/surface';
import { listUeWaypoints, updateUeWaypoint } from '@/services/api/networkElements';
import { createBuilding, createCell, createDu, createGnb, createRu, createUe, createUeActiveWindow, createUeTraffic, createUeWaypoint, deleteBuilding, deleteCell, deleteGnb, deleteUe, deleteUeActiveWindow, listUeActiveWindows, updateBuilding, updateCell, updateDu, updateGnb, updateRu, updateUe, updateUeTraffic } from '@/services/api/networkElements';
import { createAntennaPreset, createGnbConfigTemplate, listAntennaPresets, listDuConfigTemplates, listGnbConfigTemplates, listMaterials, updateAntennaPreset, updateGnbConfigTemplate } from '@/services/api/presets';
import { createRunKnob, createSceneRun, deleteRunKnob, listRunKnobs, listSceneRuns, precomputeRun, readPrecompute, startRun, stopPrecompute, stopRun, updateRunKnob, updateSceneRun, type PrecomputeStatus } from '@/services/api/runs';
import { duplicateScene, getSceneTree, listScenes, sceneHeightMap, updateScene } from '@/services/api/scenes';
import type { AntennaPreset, Building, Cell, Du, Gnb, GnbConfigTemplate, Scene, SceneRun, Ue, UeTraffic } from '@/types/registry';

export type Selection = { kind: 'gnb'; gnb: Gnb } | { kind: 'cell'; cell: Cell; gnb: Gnb } | { kind: 'ue'; ue: Ue } | { kind: 'building'; building: Building } | null;
/** 元件庫的「放置模式」:選了元件後,下一次點地面就建立 */
export type PlaceKind = 'gnb' | 'cell' | 'ue' | 'building' | null;

/** 編輯器頁的全部狀態:樹、選取、放置、屬性/天線/RAN 參數寫回、OSM 拉地圖。元件只負責畫。 */
export function useSceneEditorPage(sceneUuid: string) {
  const tree = useAsync(() => getSceneTree(sceneUuid), [sceneUuid]);
  const presets = useAsync(listAntennaPresets, []); const templates = useAsync(listDuConfigTemplates, []); const materials = useAsync(listMaterials, []); const gnbTemplates = useAsync(listGnbConfigTemplates, []);
  const runs = useAsync(() => listSceneRuns(sceneUuid), [sceneUuid]);
  const run: SceneRun | null = useMemo(() => (runs.data ?? [])[0] ?? null, [runs.data]);
  const allRuns = useAsync(() => listSceneRuns(), []);
  const scenes = useAsync(listScenes, []);
  /** 其他場景用過的幾何來源(掃描模型等),去重後給步驟 1 選 */
  const geometrySources = useMemo(() => { const m = new Map<string, { label: string; geometry_scene_id: string; geometry_source: unknown }>();
    for (const sc of scenes.data ?? []) { const g = sc.geometry_source as { type?: string; path?: string } | null; if (!g?.type || g.type === 'buildings_json') continue;
      const key = `${g.type}:${g.path ?? ''}`; if (!m.has(key)) m.set(key, { label: `${sc.geometry_scene_id || (g.path ?? '').split('/').pop()}(${sc.name} 使用中)`, geometry_scene_id: sc.geometry_scene_id, geometry_source: g }); }
    return [...m.values()]; }, [scenes.data]);
  /** 放 gNB 時要套的模板(步驟 2 選;空 = OAI 預設) */
  const [placeTemplateUuid, setPlaceTemplateUuid] = useState<string>('');
  const [progress, setProgress] = useState<string | null>(null);
  const [precomp, setPrecomp] = useState<PrecomputeStatus | null>(null);
  // precompute 進行中每 5 s 讀一次進度
  useEffect(() => {
    if (run?.status !== 'precomputing') return;
    const tick = () => { readPrecompute(run.scene_run_uuid).then(setPrecomp).catch(() => undefined); runs.refetch(); };
    tick(); const t = setInterval(tick, 5_000); return () => clearInterval(t);
  }, [run?.status, run?.scene_run_uuid]);   // eslint-disable-line react-hooks/exhaustive-deps
  const knobs = useAsync(() => (run ? listRunKnobs(run.scene_run_uuid) : Promise.resolve([])), [run?.scene_run_uuid]);
  const [selection, setSelection] = useState<Selection>(null);
  const [placeKind, setPlaceKind] = useState<PlaceKind>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const withSave = useCallback(async (label: string, fn: () => Promise<unknown>) => {
    setSaving(true); setMessage(null);
    try { await fn(); setMessage(`${label} 已儲存`); tree.refetch(); }
    catch (e) { setMessage(`${label} 失敗:${e instanceof Error ? e.message : String(e)}`); }
    finally { setSaving(false); }
  }, [tree]);
  const gnbs = tree.data?.gnbs ?? [];
  const selGnb = selection?.kind === 'gnb' ? selection.gnb : selection?.kind === 'cell' ? selection.gnb : null;

  /** 套用 gNB 模板 = 快速填值:gNB(PLMN/A3/來源)、DU 模板、每個 cell 的 RF、RU 天線。現場之後仍可逐項改。 */
  const applyGnbTemplate = async (g: Gnb, t: GnbConfigTemplate) => {
    await updateGnb(g.gnb_uuid, { plmn_mcc: t.plmn_mcc, plmn_mnc: t.plmn_mnc, a3_enabled: t.a3_enabled, a3_offset_db: t.a3_offset_db, a3_hys_db: t.a3_hys_db, a3_ttt_ms: t.a3_ttt_ms, f_gnb_config_template_uuid: t.gnb_config_template_uuid });
    for (const du of g.dus) { await updateDu(du.du_uuid, { f_du_config_template_uuid: t.f_du_config_template_uuid });
      for (const c of du.cells) { await updateCell(c.cell_uuid, { band: t.band, center_frequency_ghz: t.center_frequency_ghz, bandwidth_mhz: t.bandwidth_mhz, power_dbm: t.power_dbm, tilt_deg: t.tilt_deg });
        if (c.ru) await updateRu(c.ru.ru_uuid, { f_antenna_preset_uuid: t.f_antenna_preset_uuid }); else await createRu({ f_cell_uuid: c.cell_uuid, name: `${c.name}_ru`, f_antenna_preset_uuid: t.f_antenna_preset_uuid }); } }
  };
  /** 現場 gNB → 模板欄位(取第一個 DU / cell / RU 的值) */
  const gnbToTemplate = (g: Gnb): Partial<GnbConfigTemplate> => { const du = g.dus[0]; const c = du?.cells[0]; return {
    plmn_mcc: g.plmn_mcc, plmn_mnc: g.plmn_mnc, a3_enabled: g.a3_enabled ?? false, a3_offset_db: g.a3_offset_db ?? 1, a3_hys_db: g.a3_hys_db ?? 0.5, a3_ttt_ms: g.a3_ttt_ms ?? 80,
    band: c?.band ?? 'n78', center_frequency_ghz: c?.center_frequency_ghz ?? 3.5, bandwidth_mhz: c?.bandwidth_mhz ?? 40, power_dbm: c?.power_dbm ?? 23, tilt_deg: c?.tilt_deg ?? 0,
    cells_per_gnb: du?.cells.length ?? 1, f_du_config_template_uuid: du?.f_du_config_template_uuid ?? null, f_antenna_preset_uuid: c?.ru?.f_antenna_preset_uuid ?? null, source: 'custom' }; };
  const defaultGnbTemplate = () => (gnbTemplates.data ?? []).find((t) => t.gnb_config_template_uuid === placeTemplateUuid)
    ?? (gnbTemplates.data ?? []).find((t) => t.source === 'oai') ?? (gnbTemplates.data ?? [])[0] ?? null;

  /** 步驟 3:依參數產生 UE(可選先清掉同前綴的舊 UE);每個 UE 的路徑點並行寫入 */
  const generateUes = (p: UeGenParams, replace: boolean) => withSave(`產生 ${p.count} 個 UE`, async () => {
    // 掃描模型場景沒有建築盒 —— 向後端要高度圖,讓隨機位置與路徑避開建築
    let hm = null;
    try { hm = await sceneHeightMap(sceneUuid); }
    catch (e) { console.warn('取不到高度圖,UE 將不避障', e); }
    const plan = planUes(p, walkableFromHeightMap(hm));
    if (replace) { const old = (tree.data?.ues ?? []).filter((u) => u.name.startsWith(p.namePrefix)); for (const [i, u] of old.entries()) { setProgress(`清除舊 UE ${i + 1}/${old.length}`); await deleteUe(u.ue_uuid); } }
    for (const [i, pu] of plan.entries()) {
      setProgress(`寫入 UE ${i + 1}/${plan.length}`);
      const ue = await createUe({ f_scene_uuid: sceneUuid, name: pu.name, antenna_height_m: p.height, qos_5qi: p.qos5qi, speed_mps: pu.speed, color: [0.8, 0.8, 0.8] });
      for (let k = 0; k < pu.waypoints.length; k += 8) {
        await Promise.all(pu.waypoints.slice(k, k + 8).map(([t, x, y, z], j) => createUeWaypoint({ f_ue_uuid: ue.ue_uuid, ord: k + j, t_sec: t, x, y, z })));
      }
      await createUeActiveWindow({ f_ue_uuid: ue.ue_uuid, t0_sec: 0, t1_sec: p.duration });
      await createUeTraffic({ f_ue_uuid: ue.ue_uuid, pattern: 'piecewise', rate_mbps: 0, schedule: pu.schedule, bearer_id: 1 });
    }
    setProgress(null);
  }).finally(() => setProgress(null));

  /** 點地面:依放置模式建立物件(gNB 自帶 DU/cell/RU;cell 要先選 gNB;UE 建一個 waypoint;建築是 10×6×10 盒) */
  const placeAt = (pos: [number, number, number]) => {
    const [x, sy, z] = pos; /* sy = 點到的表面高度(地面 0 / 屋頂 / 掃描模型地板) */ const n = (k: string) => `${k}${(k === 'gnb' ? gnbs.length : k === 'ue' ? (tree.data?.ues.length ?? 0) : (tree.data?.buildings.length ?? 0)) + 1}`;
    if (placeKind === 'gnb') void withSave(`gNB ${n('gnb')}`, async () => { const t = defaultGnbTemplate(); const g = await createGnb({ f_scene_uuid: sceneUuid, name: n('gnb'), position: [x, sy + GNB_ABOVE_SURFACE_M, z] }); const d = await createDu({ f_gnb_uuid: g.gnb_uuid, name: `${g.name}_du0`, f_du_config_template_uuid: t?.f_du_config_template_uuid ?? null });
      const nCell = Math.max(1, t?.cells_per_gnb ?? 1); const cells: Cell[] = [];
      for (let k = 0; k < nCell; k++) { const c = await createCell({ f_du_uuid: d.du_uuid, name: `${g.name}_c${k}`, pci: gnbs.length * 3 + k, azimuth_deg: (k * (t?.azimuth_step_deg ?? 120)) % 360, band: t?.band, center_frequency_ghz: t?.center_frequency_ghz, bandwidth_mhz: t?.bandwidth_mhz, power_dbm: t?.power_dbm, tilt_deg: t?.tilt_deg }); await createRu({ f_cell_uuid: c.cell_uuid, name: `${c.name}_ru`, f_antenna_preset_uuid: t?.f_antenna_preset_uuid ?? null }); cells.push(c); }
      if (t) await updateGnb(g.gnb_uuid, { plmn_mcc: t.plmn_mcc, plmn_mnc: t.plmn_mnc, a3_enabled: t.a3_enabled, a3_offset_db: t.a3_offset_db, a3_hys_db: t.a3_hys_db, a3_ttt_ms: t.a3_ttt_ms, f_gnb_config_template_uuid: t.gnb_config_template_uuid }); });
    else if (placeKind === 'cell') { if (!selGnb) { setMessage('先選一個 gNB,再放 cell(DAS 拉遠)'); return; } const du = selGnb.dus[0]; const k = du.cells.length; void withSave(`cell ${selGnb.name}_c${k}`, async () => { const c = await createCell({ f_du_uuid: du.du_uuid, name: `${selGnb.name}_c${k}`, pci: k, position: [x, sy + GNB_ABOVE_SURFACE_M, z], azimuth_deg: (k * 120) % 360 }); await createRu({ f_cell_uuid: c.cell_uuid, name: `${c.name}_ru` }); }); }
    else if (placeKind === 'ue') void withSave(`UE ${n('ue')}`, async () => { const u = await createUe({ f_scene_uuid: sceneUuid, name: n('ue'), antenna_height_m: 1.5, qos_5qi: 9, color: [0.8, 0.8, 0.8] }); await createUeWaypoint({ f_ue_uuid: u.ue_uuid, ord: 0, t_sec: 0, x, y: sy + UE_ABOVE_SURFACE_M, z }); });
    else if (placeKind === 'building') void withSave(`建築 ${n('b')}`, () => createBuilding({ f_scene_uuid: sceneUuid, name: n('b'), source: 'manual_box', geometry_ref: '', position: [x, sy, z], size: [10, 6, 10], rotation: [0, 0, 0], scale: [1, 1, 1] }));
    setPlaceKind(null);
  };


  return {
    tree: tree.data, status: tree.status, error: tree.error, presets: presets.data ?? [], templates: templates.data ?? [], materials: materials.data ?? [], gnbTemplates: gnbTemplates.data ?? [],
    run, knobs: knobs.data ?? [], selection, select: (s: Selection) => { setSelection(s); }, saving, message, placeKind, setPlaceKind, placeAt,
    /** 目前選到的 gNB(放 cell 的前置條件:DAS 拉遠單元要掛在某個 gNB 的 DU 底下) */
    selGnb,
    moveCell: (c: Cell, pos: [number, number, number]) => withSave(`cell ${c.name} 位置`, () => updateCell(c.cell_uuid, { position: pos })),
    /** UE 拖到新位置:整條路徑平移(每個 waypoint 加同一個位移) */
    moveUe: (u: Ue, d: [number, number, number]) => withSave(`UE ${u.name} 位置`, async () => {
      const rows = await listUeWaypoints(u.ue_uuid);
      for (let k = 0; k < rows.length; k += 8) await Promise.all(rows.slice(k, k + 8).map((w) => updateUeWaypoint(w.ue_waypoint_uuid, { x: w.x + d[0], y: w.y + d[1], z: w.z + d[2] })));
    }),
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
    applyGnbTemplate: (g: Gnb, t: GnbConfigTemplate) => withSave(`gNB ${g.name} 套用「${t.name}」`, () => applyGnbTemplate(g, t)),
    /** 現場 gNB 存成新模板 / 更新既有模板(值取自現場) */
    saveGnbAsTemplate: (g: Gnb, name: string, uuid: string | null) => withSave(uuid ? `更新模板` : `新模板 ${name}`, async () => { const body = { ...gnbToTemplate(g), name }; const t = uuid ? await updateGnbConfigTemplate(uuid, body) : await createGnbConfigTemplate(body); await updateGnb(g.gnb_uuid, { f_gnb_config_template_uuid: t.gnb_config_template_uuid }); gnbTemplates.refetch(); }),
    /** 天線:現場欄位寫進 RU 覆寫;或存成 / 更新 preset 並綁到 RU */
    applyAntennaFields: (c: Cell, fields: Partial<AntennaPreset>) => withSave(`cell ${c.name} 天線覆寫`, async () => c.ru ? updateRu(c.ru.ru_uuid, { antenna_override: fields }) : createRu({ f_cell_uuid: c.cell_uuid, name: `${c.name}_ru`, antenna_override: fields })),
    saveAntennaAsPreset: (c: Cell, fields: Partial<AntennaPreset>, name: string, uuid: string | null) => withSave(uuid ? '更新天線 preset' : `新天線 preset ${name}`, async () => { const a = uuid ? await updateAntennaPreset(uuid, { ...fields, name }) : await createAntennaPreset({ ...fields, name, source: 'custom' }); if (c.ru) await updateRu(c.ru.ru_uuid, { f_antenna_preset_uuid: a.antenna_preset_uuid, antenna_override: null }); else await createRu({ f_cell_uuid: c.cell_uuid, name: `${c.name}_ru`, f_antenna_preset_uuid: a.antenna_preset_uuid }); presets.refetch(); }),
    reloadTree: tree.refetch, allRuns: allRuns.data ?? [], geometrySources, progress, precomp, placeTemplateUuid, setPlaceTemplateUuid, generateUes,
    clearUes: (prefix: string) => withSave(`清除 ${prefix}* UE`, async () => { for (const u of (tree.data?.ues ?? []).filter((x) => x.name.startsWith(prefix))) await deleteUe(u.ue_uuid); }),
    /** UE 流量:沒有就新建;cbr 用 rate,piecewise 用 schedule */
    setUeTraffic: (u: Ue, t: Partial<UeTraffic>) => withSave(`UE ${u.name} 流量`, async () => { const cur = u.traffic[0];
      if (cur) await updateUeTraffic(cur.ue_traffic_uuid, t); else await createUeTraffic({ f_ue_uuid: u.ue_uuid, pattern: t.pattern ?? 'cbr', rate_mbps: t.rate_mbps ?? 1, schedule: t.schedule ?? null, bearer_id: 1 }); }),
    /** UE 在場時段:整組替換;空陣列 = 全程在場 */
    setUeWindows: (u: Ue, windows: [number, number][]) => withSave(`UE ${u.name} 在場時段`, async () => {
      for (const w of await listUeActiveWindows(u.ue_uuid)) if (w.f_ue_uuid === u.ue_uuid) await deleteUeActiveWindow(w.ue_active_window_uuid);   // 只刪自己的(防 reader 沒過濾)
      for (const [a, b] of windows) await createUeActiveWindow({ f_ue_uuid: u.ue_uuid, t0_sec: a, t1_sec: b }); }),
    updateSceneInfo: (f: Partial<Scene>) => withSave('場景資訊', () => updateScene(sceneUuid, f)),
    duplicate: async (name: string): Promise<string | null> => { let id: string | null = null; await withSave(`複製為 ${name}`, async () => { id = (await duplicateScene(sceneUuid, name)).scene_uuid; }); return id; },
    precompute: () => withSave('Precompute 啟動', async () => { if (run) { await precomputeRun(run.scene_run_uuid); runs.refetch(); } }),
    stopPrecompute: () => withSave('Precompute 停止', async () => { if (run) { await stopPrecompute(run.scene_run_uuid); runs.refetch(); } }),
    start: () => withSave('啟動', async () => { if (run) { await startRun(run.scene_run_uuid, run.speed_x, run.sim_dt_ms); runs.refetch(); allRuns.refetch(); } }),
    stop: () => withSave('停止', async () => { if (run) { await stopRun(run.scene_run_uuid); runs.refetch(); allRuns.refetch(); } }),
    refreshRuns: () => { runs.refetch(); allRuns.refetch(); },
    setUeAntenna: (u: Ue, uuid: string | null) => withSave(`UE ${u.name} 天線`, () => updateUe(u.ue_uuid, { f_antenna_preset_uuid: uuid })),
    /** run 層:沒有 run 就先建 draft;knob 以 key 唯一 */
    /** 場景層級天線(run 只能一組;Sionna scene-global) */
    // 釘 E2 槽位:唯一值,被別的場景占走 registry 會回錯誤(唯一約束)
    setE2Block: (block: number | null) => withSave('E2 區塊', () => updateScene(sceneUuid, { e2_block: block })),
    setCategory: (category: string | null) => withSave('場景分類', () => updateScene(sceneUuid, { category })),
    setSceneAntenna: (which: 'gnb' | 'ue', uuid: string | null) => withSave(`場景 ${which.toUpperCase()} 天線`, () => updateScene(sceneUuid, which === 'gnb' ? { f_gnb_antenna_preset_uuid: uuid } : { f_ue_antenna_preset_uuid: uuid })),
    updateRunFields: (f: Partial<SceneRun>) => withSave('run 設定', async () => { if (run) await updateSceneRun(run.scene_run_uuid, f); else await createSceneRun({ f_scene_uuid: sceneUuid, ...f }); runs.refetch(); }),
    setKnob: (key: string, value: string) => withSave(`knob ${key}`, async () => {
      let r = run; if (!r) { r = await createSceneRun({ f_scene_uuid: sceneUuid }); runs.refetch(); }
      const ex = (knobs.data ?? []).find((k) => k.key === key); let v: unknown = value; try { v = JSON.parse(value); } catch { /* 純字串 */ }
      if (ex) await updateRunKnob(ex.run_knob_uuid, v); else await createRunKnob({ f_scene_run_uuid: r.scene_run_uuid, key, value: v }); knobs.refetch(); }),
    removeKnob: (uuid: string) => withSave('knob 刪除', async () => { await deleteRunKnob(uuid); knobs.refetch(); }),
  };
}
