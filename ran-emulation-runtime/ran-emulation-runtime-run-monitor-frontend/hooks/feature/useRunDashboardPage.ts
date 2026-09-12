'use client';
import { useCallback, useMemo, useState } from 'react';
import { POLL_MS } from '@/config';
import { useAsync } from '@/hooks/base/useAsync';
import { usePolling } from '@/hooks/base/usePolling';
import { listControlEvents, listHandoverEvents, listKpmSamples, listLaunchRequests } from '@/services/api/archive';
import { getDuTick, getE2AdapterStatus, getRun, listScenes } from '@/services/api/runs';
import type { KpmSample } from '@/types/telemetry';

/** 單 run 的全部資料 + 衍生(最新視窗、每 cell 的時間序列、命令前後對照)。元件只畫。 */
export function useRunDashboardPage(runUuid: string) {
  const run = useAsync(() => getRun(runUuid), [runUuid]);
  const scenes = useAsync(listScenes, []);
  const samples = useAsync(() => listKpmSamples(runUuid), [runUuid]);
  const hos = useAsync(() => listHandoverEvents(runUuid), [runUuid]);
  const ctrls = useAsync(() => listControlEvents(runUuid), [runUuid]);
  const launches = useAsync(() => listLaunchRequests(runUuid), [runUuid]);
  const tick = useAsync(getDuTick, []); const e2 = useAsync(getE2AdapterStatus, []);
  const live = run.data?.status === 'running';
  const refetchAll = useCallback(() => { run.refetch(); samples.refetch(); hos.refetch(); ctrls.refetch(); tick.refetch(); e2.refetch(); }, [run, samples, hos, ctrls, tick, e2]);
  usePolling(refetchAll, POLL_MS, live);
  const [expandedUe, setExpandedUe] = useState(false);
  const [selectedWindow, setSelectedWindow] = useState<number | null>(null);
  const list = useMemo(() => samples.data ?? [], [samples.data]);
  const latest: KpmSample | null = list.length ? list[selectedWindow ?? list.length - 1] ?? list[list.length - 1] : null;
  const cellSeries = useMemo(() => {
    const m: Record<string, { t: number; v: number }[]> = {};
    for (const s of list) for (const [c, k] of Object.entries(s.per_cell)) (m[c] ??= []).push({ t: s.sim_time_ms, v: k.prb_pct_dl });
    return m;
  }, [list]);
  const cellUeCount = useMemo(() => { const m: Record<string, number> = {}; if (latest) for (const u of Object.values(latest.per_ue)) m[u.serving_cell] = (m[u.serving_cell] ?? 0) + 1; return m; }, [latest]);
  /** 命令前後對照:命令時間點前後各 N 窗的 per-cell PrbTotDl 平均差 */
  const commandImpact = useMemo(() => (ctrls.data ?? []).map((c) => {
    const at = c.at_sim_ms; const N = 5;
    const before = list.filter((s) => s.sim_time_ms < at).slice(-N); const after = list.filter((s) => s.sim_time_ms >= at).slice(0, N);
    const avg = (xs: KpmSample[]) => { const v = xs.flatMap((s) => Object.values(s.per_cell).map((k) => k.prb_pct_dl)); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };
    return { event: c, prbBefore: avg(before), prbAfter: avg(after) };
  }), [ctrls.data, list]);
  return {
    run: run.data, sceneName: (scenes.data ?? []).find((s) => s.scene_uuid === run.data?.f_scene_uuid)?.legacy_scenario_id ?? '', status: run.status, error: run.error,
    samples: list, latest, cellSeries, cellUeCount, handovers: hos.data ?? [], controls: ctrls.data ?? [], launches: launches.data ?? [],
    duTick: tick.data, e2: e2.data, live, expandedUe, setExpandedUe, selectedWindow, setSelectedWindow, commandImpact,
  };
}
