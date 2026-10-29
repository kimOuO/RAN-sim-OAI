'use client';
import { useCallback, useMemo, useState } from 'react';
import { E2ADAPTER_API } from '@/config';
import { useAsync } from '@/hooks/base/useAsync';
import { usePolling } from '@/hooks/base/usePolling';
import { controlOrigin, countControlOrigins, ctrlOk } from '@/hooks/feature/controlEvents';
import { listControlEvents } from '@/services/api/archive';
import { getE2AdapterStatus, getRicObservation, getRun, listCuSubscriptions, listRunInstances, listScenes, runtimeBase } from '@/services/api/runs';
import type { ControlEvent, E2AdapterStatus, E2Subscription, RunInstance } from '@/types/telemetry';

const POLL_FAST = 5000;    // 命令清單、E2 連線
const POLL_SLOW = 30_000;  // RIC 閘道(查 RIC 端 k8s / e2mgr,不要打太頻繁)

export { ctrlOk, controlOriginLabel as ctrlKind } from '@/hooks/feature/controlEvents';

export interface RicNodeRow { inst: RunInstance; e2: E2AdapterStatus | null; subs: E2Subscription[] | null }

/** 單 run 的 RIC 視角:閘道登記 / E2 node / xApp pod、每個 gNB 的 E2 連線與訂閱、RIC 下的命令與落地結果。只讀。 */
export function useRunRicPage(runUuid: string) {
  const run = useAsync(() => getRun(runUuid), [runUuid]);
  const scenes = useAsync(listScenes, []);
  const instances = useAsync(() => listRunInstances(runUuid), [runUuid]);
  const ric = useAsync(() => getRicObservation(runUuid), [runUuid]);
  const ctrls = useAsync(() => listControlEvents(runUuid), [runUuid]);
  const live = run.data?.status === 'running';

  // per-run 容器:每個 gNB 一個 CU 與一個 e2adapter。run 停了容器就沒了,不退回共用服務(會讀到別的場景)
  const cuInsts = useMemo(() => (instances.data ?? []).filter((i) => i.role === 'cu'), [instances.data]);
  const e2Insts = useMemo(() => (instances.data ?? []).filter((i) => i.role === 'e2adapter'), [instances.data]);
  const nodes = useAsync(async (): Promise<RicNodeRow[]> => {
    if (!live) return [];
    return Promise.all(e2Insts.map(async (inst) => {
      const cu = cuInsts.find((c) => c.e2_node_id && c.e2_node_id === inst.e2_node_id) ?? cuInsts[e2Insts.indexOf(inst)];
      const [e2, subs] = await Promise.all([
        getE2AdapterStatus(runtimeBase(inst, E2ADAPTER_API, 'E2Adapter')).catch(() => null),
        cu?.host_port ? listCuSubscriptions(runtimeBase(cu, '', 'CU')).then((r) => r.subscriptions).catch(() => null) : Promise.resolve(null),
      ]);
      return { inst, e2, subs };
    }));
  }, [live, e2Insts.map((i) => i.host_port).join(','), cuInsts.map((i) => i.host_port).join(',')]);

  const fast = useCallback(() => { ctrls.refetch(); nodes.refetch(); run.refetch(); }, [ctrls, nodes, run]);
  usePolling(fast, POLL_FAST, live);
  usePolling(ric.refetch, POLL_SLOW, live);

  // 命令篩選
  const [fOrigin, setFOrigin] = useState('');
  const [fSource, setFSource] = useState(''); const [fAction, setFAction] = useState(''); const [fOutcome, setFOutcome] = useState('');
  const all = useMemo(() => [...(ctrls.data ?? [])].sort((a, b) => b.at_sim_ms - a.at_sim_ms), [ctrls.data]);
  const shown = useMemo(() => all.filter((e) => (!fOrigin || controlOrigin(e.source) === fOrigin) && (!fSource || e.source === fSource) && (!fAction || e.action_type === fAction) && (!fOutcome || e.outcome === fOutcome)), [all, fOrigin, fSource, fAction, fOutcome]);
  const uniq = (k: keyof ControlEvent) => [...new Set(all.map((e) => String(e[k])))].sort();

  const stats = useMemo(() => {
    const n = all.length; const ok = all.filter((e) => ctrlOk(e.outcome)).length;
    const lat = all.map((e) => e.landing_latency_ms).filter((x): x is number => x != null);
    const bySource = new Map<string, { n: number; ok: number }>();
    for (const e of all) { const s = bySource.get(e.source) ?? { n: 0, ok: 0 }; s.n++; if (ctrlOk(e.outcome)) s.ok++; bySource.set(e.source, s); }
    const byAction = new Map<string, number>(); for (const e of all) byAction.set(e.action_type, (byAction.get(e.action_type) ?? 0) + 1);
    const counts = countControlOrigins(all);
    return {
      n, ok, failed: n - ok, ricN: counts.ric, ricApplyN: counts.ric_apply, sonN: counts.son, otherN: counts.other, okPct: n ? (100 * ok) / n : null,
      latMean: lat.length ? lat.reduce((a, b) => a + b, 0) / lat.length : null,
      latMax: lat.length ? Math.max(...lat) : null,
      bySource: [...bySource.entries()].sort((a, b) => b[1].n - a[1].n),
      byAction: [...byAction.entries()].sort((a, b) => b[1] - a[1]),
    };
  }, [all]);

  const scene = (scenes.data ?? []).find((s) => s.scene_uuid === run.data?.f_scene_uuid);
  return {
    run: run.data, error: run.error, live,
    sceneName: scene?.legacy_scenario_id || scene?.name || run.data?.scene_run_uuid.slice(-8) || '',
    ric: ric.data ?? null, ricStatus: ric.status, nodes: nodes.data ?? [],
    all, shown, stats, sources: uniq('source'), actions: uniq('action_type'), outcomes: uniq('outcome'),
    fOrigin, setFOrigin, fSource, setFSource, fAction, setFAction, fOutcome, setFOutcome,
  };
}
export type RunRicPage = ReturnType<typeof useRunRicPage>;
