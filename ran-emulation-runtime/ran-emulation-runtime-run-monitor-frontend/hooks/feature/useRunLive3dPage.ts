'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { UE_API } from '@/config';
import { useAsync } from '@/hooks/base/useAsync';
import { usePolling } from '@/hooks/base/usePolling';
import { cellColorMap } from '@/hooks/feature/kpmDerive';
import { cellOwners, stripTag, ueAttached } from '@/hooks/feature/live3d';
import type { UeLabelMode } from '@/components/scene3d/LiveScene3D';
import { listLatestKpmSamples } from '@/services/api/archive';
import { getRun, getSceneTree3d, getUeDriverStatus, getUeRuntimeStatus, listRunInstances, listScenes, runtimeBase } from '@/services/api/runs';
import type { UeKpm } from '@/types/telemetry';
import { advanceSimAnchor, readSimAnchor } from '@/hooks/feature/simClock';

const POLL = 2000;
const FLASH_MS = 2500;
export type UeFlash = 'ho' | 'rlf';

/** 3D 即時頁:場景樹、模擬時鐘(UE driver 的 elapsed_sim_sec + 倍速外插)、每個 UE 最新的 cell / SINR、換手 / RLF 閃爍 */
export function useRunLive3dPage(runUuid: string) {
  const run = useAsync(() => getRun(runUuid), [runUuid]);
  const scenes = useAsync(listScenes, []);
  const tree = useAsync(() => (run.data ? getSceneTree3d(run.data.f_scene_uuid) : Promise.resolve(null)), [run.data?.f_scene_uuid]);
  const instances = useAsync(() => listRunInstances(runUuid), [runUuid]);
  const live = run.data?.status === 'running';
  const ueBase = runtimeBase((instances.data ?? []).find((i) => i.role === 'ue'), UE_API, 'UE');
  const drv = useAsync(() => live ? getUeDriverStatus(ueBase) : Promise.resolve(null), [ueBase, live]);
  const runtime = useAsync(() => live ? getUeRuntimeStatus(ueBase) : Promise.resolve(null), [ueBase, live]);
  const kpm = useAsync(() => listLatestKpmSamples(runUuid), [runUuid]);
  const poll = useCallback(() => { drv.refetch(); kpm.refetch(); runtime.refetch(); }, [drv, kpm, runtime]);
  usePolling(poll, POLL, live);
  usePolling(run.refetch, 10_000, true);
  usePolling(instances.refetch, 5000, live);

  /** 時鐘錨點:最近一次讀到的模擬秒數與當下 wall time;畫面每幀用 simNow() 外插 */
  const anchor = useRef({ from: 0, to: 0, wall: 0, duration: POLL });
  const session = useRef('');
  useEffect(() => {
    const d = drv.data; if (!d) return;
    const wall = performance.now(), sim = d.elapsed_sim_sec ?? 0;
    const key = `${runUuid}:${d.started_at_ms ?? ''}`;
    if (session.current !== key) {
      session.current = key;
      anchor.current = { from: sim, to: sim, wall, duration: POLL };
    } else anchor.current = advanceSimAnchor(anchor.current, sim, wall, POLL);
  }, [drv.data, runUuid]);
  const simNow = useCallback(() => readSimAnchor(anchor.current, performance.now()), []);

  /** 最新一筆有 UE 的 KPM → ue → 狀態(cell 名稱去掉 run 標籤) */
  const ueState = useMemo(() => {
    const m: Record<string, UeKpm & { cell: string }> = {};
    for (const w of kpm.data ?? []) for (const [id, k] of Object.entries(w.per_ue ?? {})) m[id] = { ...k, cell: stripTag(k.serving_cell || '') };
    if (runtime.data) for (const [id, k] of Object.entries(m)) {
      const t = runtime.data.threads.find((u) => u.ue_id === id);
      k.attached = !!t && t.rrc_state === 'CONNECTED' && t.visible !== false;
      k.cell = k.attached ? stripTag(t?.serving_cell || k.cell) : '';
    }
    return m;
  }, [kpm.data, runtime.data]);

  /** 與上一輪比:cell 換了 = 換手;SINR 變哨兵 / 沒 cell = RLF。閃 FLASH_MS */
  const prev = useRef<Record<string, string>>({});
  const [flashes, setFlashes] = useState<Record<string, { kind: UeFlash; until: number }>>({});
  useEffect(() => {
    const now = performance.now(); const add: Record<string, { kind: UeFlash; until: number }> = {};
    for (const [id, s] of Object.entries(ueState)) {
      const before = prev.current[id];
      if (!ueAttached(s) && before) add[id] = { kind: 'rlf', until: now + FLASH_MS };
      else if (before && s.cell && before !== s.cell) add[id] = { kind: 'ho', until: now + FLASH_MS };
      prev.current[id] = ueAttached(s) ? s.cell : '';
    }
    if (Object.keys(add).length) setFlashes((f) => ({ ...Object.fromEntries(Object.entries(f).filter(([, v]) => v.until > now)), ...add }));
  }, [ueState]);

  const cellNames = useMemo(() => (tree.data?.gnbs ?? []).flatMap((g) => g.dus.flatMap((d) => d.cells.map((c) => c.name))), [tree.data]);
  const color = useMemo(() => cellColorMap(cellNames), [cellNames]);
  const [selected, setSelected] = useState<string | null>(null);
  const owners = useMemo(() => cellOwners(tree.data), [tree.data]);
  const [labelMode, setLabelMode] = useState<UeLabelMode>('brief');
  const [showSites, setShowSites] = useState(true);

  return {
    run: run.data, status: run.status, error: run.error ?? tree.error,
    sceneName: (() => { const s = (scenes.data ?? []).find((s) => s.scene_uuid === run.data?.f_scene_uuid); return s?.legacy_scenario_id || s?.name || ''; })(),
    tree: tree.data, driver: drv.data, live, simNow, ueState, flashes, color, selected, setSelected, owners, labelMode, setLabelMode, showSites, setShowSites,
  };
}
export type RunLive3dPage = ReturnType<typeof useRunLive3dPage>;
