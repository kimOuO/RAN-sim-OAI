'use client';
import { useCallback, useMemo, useState } from 'react';
import { POLL_MS, RANGE_OPTIONS, UE_METRICS } from '@/config';
import { useAsync } from '@/hooks/base/useAsync';
import { usePolling } from '@/hooks/base/usePolling';
import { listControlEvents, listHandoverEvents, listKpmSamples, listLaunchRequests } from '@/services/api/archive';
import { DU_API, E2ADAPTER_API, UE_API } from '@/config';
import { getDuTick, getE2AdapterStatus, getRicObservation, getRun, getSceneTree, getUeDriverStatus, listDuCells, listRunInstances, listScenes, runtimeBase } from '@/services/api/runs';
import { allCells, allUes, bucketEvents, cellColorMap, cellSeries, groupCellsByGnb, histogram, latestUes, mean, meanMcsByCell, meanRlcDelayByCell, meanSinrByCell, prbDl, prbUl, thpDlByCell, thpUlByCell, ueCountByCell, ueSeries, ueServingStrip } from '@/hooks/feature/kpmDerive';
import type { KpmSample } from '@/types/telemetry';

/** 單 run 的全部資料 + 衍生序列。元件只畫。 */
export function useRunDashboardPage(runUuid: string) {
  const run = useAsync(() => getRun(runUuid), [runUuid]);
  const scenes = useAsync(listScenes, []);
  const tree = useAsync(() => (run.data ? getSceneTree(run.data.f_scene_uuid) : Promise.resolve(null)), [run.data?.f_scene_uuid]);
  const samples = useAsync(() => listKpmSamples(runUuid), [runUuid]);
  const hos = useAsync(() => listHandoverEvents(runUuid), [runUuid]);
  const ctrls = useAsync(() => listControlEvents(runUuid), [runUuid]);
  const launches = useAsync(() => listLaunchRequests(runUuid), [runUuid]);
  const instances = useAsync(() => listRunInstances(runUuid), [runUuid]);
  const ric = useAsync(() => getRicObservation(runUuid), [runUuid]);
  const duBase = runtimeBase((instances.data ?? []).find((i) => i.role === 'du'), DU_API, 'DU');
  const ueBase = runtimeBase((instances.data ?? []).find((i) => i.role === 'ue'), UE_API, 'UE');
  const e2Base = runtimeBase((instances.data ?? []).find((i) => i.role === 'e2adapter'), E2ADAPTER_API, 'E2Adapter');
  const tick = useAsync(() => getDuTick(duBase), [duBase]); const e2 = useAsync(() => getE2AdapterStatus(e2Base), [e2Base]); const ueDrv = useAsync(() => getUeDriverStatus(ueBase), [ueBase]); const duCells = useAsync(() => listDuCells(duBase), [duBase]);
  const live = run.data?.status === 'running';
  const refetchAll = useCallback(() => { run.refetch(); samples.refetch(); hos.refetch(); ctrls.refetch(); tick.refetch(); e2.refetch(); ueDrv.refetch(); instances.refetch(); }, [run, samples, hos, ctrls, tick, e2, ueDrv, instances]);
  usePolling(refetchAll, POLL_MS, live);
  usePolling(ric.refetch, 30000, live);   // 閘道查詢慢,30 s 一次

  const [range, setRange] = useState<number>(RANGE_OPTIONS[1].windows);
  const [selectedUe, setSelectedUe] = useState<string | null>(null);
  const [selectedWindow, setSelectedWindow] = useState<number | null>(null);

  const all = useMemo(() => samples.data ?? [], [samples.data]);
  const view = useMemo(() => (range && all.length > range ? all.slice(-range) : all), [all, range]);
  const cells = useMemo(() => allCells(all), [all]);
  const color = useMemo(() => cellColorMap(cells), [cells]);
  const ues = useMemo(() => allUes(all), [all]);
  const gnbGroups = useMemo(() => groupCellsByGnb(cells, tree.data ?? null), [cells, tree.data]);
  const latest: KpmSample | null = all.length ? (selectedWindow != null ? all[Math.min(selectedWindow, all.length - 1)] : all[all.length - 1]) : null;
  const prev: KpmSample | null = all.length > 1 ? all[all.length - 2] : null;

  const charts = useMemo(() => ({
    prbDl: cellSeries(view, cells, color, prbDl), prbUl: cellSeries(view, cells, color, prbUl),
    thpDl: cellSeries(view, cells, color, thpDlByCell), thpUl: cellSeries(view, cells, color, thpUlByCell), ueCount: cellSeries(view, cells, color, ueCountByCell), sinr: cellSeries(view, cells, color, meanSinrByCell),
    rlcDelay: cellSeries(view, cells, color, meanRlcDelayByCell), mcs: cellSeries(view, cells, color, meanMcsByCell),
  }), [view, cells, color]);
  const xLabels = useMemo(() => view.map((w) => w.sim_time_ms / 1000), [view]);

  const ueRows = useMemo(() => latestUes(latest).map(([id, k]) => ({ id, k, color: color[k.serving_cell] ?? '#888' })), [latest, color]);
  const cellUeCount = useMemo(() => { const m: Record<string, number> = {}; for (const r of ueRows) m[r.k.serving_cell] = (m[r.k.serving_cell] ?? 0) + 1; return m; }, [ueRows]);
  const sinrHist = useMemo(() => histogram(ueRows.map((r) => r.k.sinr_db), -10, 40, 10), [ueRows]);
  const ueDetail = useMemo(() => selectedUe ? { id: selectedUe, metrics: UE_METRICS.map((m) => ({ ...m, points: ueSeries(view, selectedUe, m.key) })), serving: ueServingStrip(view, selectedUe), last: latest?.per_ue[selectedUe] ?? null } : null, [selectedUe, view, latest]);
  const ueSmall = useMemo(() => ues.map((u) => ({ id: u, sinr: ueSeries(view, u, 'sinr_db'), serving: ueServingStrip(view, u), last: latest?.per_ue[u] ?? null })), [ues, view, latest]);

  const totalSec = Math.max(60, (all[all.length - 1]?.sim_time_ms ?? 0) / 1000);
  const hoOk = useMemo(() => (hos.data ?? []).filter((h) => h.outcome !== 'RLF'), [hos.data]);
  const rlf = useMemo(() => (hos.data ?? []).filter((h) => h.outcome === 'RLF'), [hos.data]);
  const eventBars = useMemo(() => ({ ho: bucketEvents(hoOk.map((h) => h.at_sim_ms), 60, totalSec), rlf: bucketEvents(rlf.map((h) => h.at_sim_ms), 60, totalSec) }), [hoOk, rlf, totalSec]);

  const stat = (w: KpmSample | null) => { const us = w ? Object.values(w.per_ue) : []; const cs = w ? Object.values(w.per_cell) : []; return {
    ue: us.length, sinr: mean(us.map((u) => u.sinr_db)), thp: us.reduce((a, u) => a + (u.throughput_dl_mbps ?? 0), 0), prb: mean(cs.map((c) => c.prb_pct_dl)), mcs: mean(us.map((u) => u.mcs_dl)) }; };
  const stats = { now: stat(latest), prev: stat(prev) };
  /** RIC 命令前後對照:前後各 5 窗的 cell 平均 PrbTotDl */
  const commandImpact = useMemo(() => (ctrls.data ?? []).map((c) => {
    const at = c.at_sim_ms; const N = 5;
    const avg = (xs: KpmSample[]) => mean(xs.flatMap((s) => Object.values(s.per_cell).map((k) => k.prb_pct_dl)));
    return { event: c, prbBefore: avg(all.filter((s) => s.sim_time_ms < at).slice(-N)), prbAfter: avg(all.filter((s) => s.sim_time_ms >= at).slice(0, N)) };
  }), [ctrls.data, all]);

  return {
    run: run.data, sceneName: (scenes.data ?? []).find((s) => s.scene_uuid === run.data?.f_scene_uuid)?.legacy_scenario_id ?? '', status: run.status, error: run.error,
    all, view, latest, cells, color, gnbGroups, cellUeCount, sceneTree: tree.data ?? null, charts, xLabels, ueRows, sinrHist, ueSmall, ueDetail, selectedUe, setSelectedUe, stats,
    handovers: hos.data ?? [], hoOk, rlf, eventBars, controls: ctrls.data ?? [], commandImpact, launches: launches.data ?? [],
    duTick: tick.data, duCells: duCells.data ?? [], ueDriver: ueDrv.data, e2: e2.data, instances: instances.data ?? [], ric: ric.data ?? null, perRun: (instances.data ?? []).some((i) => i.host_port), live, range, setRange, selectedWindow, setSelectedWindow,
  };
}
