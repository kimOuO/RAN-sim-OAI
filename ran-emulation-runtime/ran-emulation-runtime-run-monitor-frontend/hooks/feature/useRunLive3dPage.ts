'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { UE_API } from '@/config';
import { useAsync } from '@/hooks/base/useAsync';
import { usePolling } from '@/hooks/base/usePolling';
import { cellColorMap } from '@/hooks/feature/kpmDerive';
import { stripTag } from '@/hooks/feature/live3d';
import { listLatestKpmSamples } from '@/services/api/archive';
import { getRun, getSceneTree3d, getUeDriverStatus, listRunInstances, listScenes, runtimeBase } from '@/services/api/runs';
import type { UeKpm } from '@/types/telemetry';

const POLL = 2000;
const FLASH_MS = 2500;
export type UeFlash = 'ho' | 'rlf';

/** 3D 即時頁:場景樹、模擬時鐘(UE driver 的 elapsed_sim_sec + 倍速外插)、每個 UE 最新的 cell / SINR、換手 / RLF 閃爍 */
export function useRunLive3dPage(runUuid: string) {
  const run = useAsync(() => getRun(runUuid), [runUuid]);
  const scenes = useAsync(listScenes, []);
  const tree = useAsync(() => (run.data ? getSceneTree3d(run.data.f_scene_uuid) : Promise.resolve(null)), [run.data?.f_scene_uuid]);
  const instances = useAsync(() => listRunInstances(runUuid), [runUuid]);
  const ueBase = runtimeBase((instances.data ?? []).find((i) => i.role === 'ue'), UE_API, 'UE');
  const drv = useAsync(() => getUeDriverStatus(ueBase), [ueBase]);
  const kpm = useAsync(() => listLatestKpmSamples(runUuid), [runUuid]);
  const live = run.data?.status === 'running';
  const poll = useCallback(() => { drv.refetch(); kpm.refetch(); }, [drv, kpm]);
  usePolling(poll, POLL, live);
  usePolling(run.refetch, 10_000, true);

  /** 時鐘錨點:最近一次讀到的模擬秒數與當下 wall time;畫面每幀用 simNow() 外插 */
  const anchor = useRef({ sim: 0, wall: 0, speed: 0 });
  useEffect(() => {
    const d = drv.data; if (!d) return;
    anchor.current = { sim: d.elapsed_sim_sec ?? 0, wall: performance.now(), speed: d.running ? (d.sim_speed_x || 1) : 0 };
  }, [drv.data]);
  const simNow = useCallback(() => { const a = anchor.current; return a.sim + ((performance.now() - a.wall) / 1000) * a.speed; }, []);

  /** 最新一筆有 UE 的 KPM → ue → 狀態(cell 名稱去掉 run 標籤) */
  const ueState = useMemo(() => {
    const w = [...(kpm.data ?? [])].reverse().find((s) => Object.keys(s.per_ue).length);
    const m: Record<string, UeKpm & { cell: string }> = {};
    for (const [id, k] of Object.entries(w?.per_ue ?? {})) m[id] = { ...k, cell: stripTag(k.serving_cell || '') };
    return m;
  }, [kpm.data]);

  /** 與上一輪比:cell 換了 = 換手;SINR 變哨兵 / 沒 cell = RLF。閃 FLASH_MS */
  const prev = useRef<Record<string, string>>({});
  const [flashes, setFlashes] = useState<Record<string, { kind: UeFlash; until: number }>>({});
  useEffect(() => {
    const now = performance.now(); const add: Record<string, { kind: UeFlash; until: number }> = {};
    for (const [id, s] of Object.entries(ueState)) {
      const before = prev.current[id];
      if ((!s.cell || s.sinr_db <= -99) && before) add[id] = { kind: 'rlf', until: now + FLASH_MS };
      else if (before && s.cell && before !== s.cell) add[id] = { kind: 'ho', until: now + FLASH_MS };
      prev.current[id] = s.cell && s.sinr_db > -99 ? s.cell : '';
    }
    if (Object.keys(add).length) setFlashes((f) => ({ ...Object.fromEntries(Object.entries(f).filter(([, v]) => v.until > now)), ...add }));
  }, [ueState]);

  const cellNames = useMemo(() => (tree.data?.gnbs ?? []).flatMap((g) => g.dus.flatMap((d) => d.cells.map((c) => c.name))), [tree.data]);
  const color = useMemo(() => cellColorMap(cellNames), [cellNames]);
  const [selected, setSelected] = useState<string | null>(null);
  const [showLabels, setShowLabels] = useState(false);

  return {
    run: run.data, status: run.status, error: run.error ?? tree.error,
    sceneName: (scenes.data ?? []).find((s) => s.scene_uuid === run.data?.f_scene_uuid)?.legacy_scenario_id ?? '',
    tree: tree.data, driver: drv.data, live, simNow, ueState, flashes, color, selected, setSelected, showLabels, setShowLabels,
  };
}
export type RunLive3dPage = ReturnType<typeof useRunLive3dPage>;
