'use client';
import { useEffect, useMemo, useState } from 'react';
import { useAsync } from '@/hooks/base/useAsync';
import { listExecutions } from '@/services/api/archive';
import { getSceneTree3d, listRuns, listScenes } from '@/services/api/runs';
import type { RunExecution, SceneTree3d } from '@/types/telemetry';

export interface ExecRow { e: RunExecution; sceneUuid: string; name: string; category: string; mode?: string; latest: boolean }

/** 回放清單:所有(或某個 run 的)執行紀錄 + 劇本名稱 / 組別 + 場景縮圖用的場景樹(每個場景只抓一次) */
export function usePlaybackLibrary(runUuid?: string) {
  const execs = useAsync(() => listExecutions(runUuid), [runUuid]);
  const runs = useAsync(listRuns, []);
  const scenes = useAsync(listScenes, []);
  const [q, setQ] = useState(''); const [cat, setCat] = useState(''); const [days, setDays] = useState(0);

  const rows = useMemo<ExecRow[]>(() => {
    const runMap = new Map((runs.data ?? []).map((r) => [r.scene_run_uuid, r]));
    const sceneMap = new Map((scenes.data ?? []).map((s) => [s.scene_uuid, s]));
    const latestSeq = new Map<string, number>();
    for (const e of execs.data ?? []) latestSeq.set(e.f_scene_run_uuid, Math.max(latestSeq.get(e.f_scene_run_uuid) ?? 0, e.run_seq));
    return (execs.data ?? []).map((e) => {
      const r = runMap.get(e.f_scene_run_uuid); const s = r ? sceneMap.get(r.f_scene_uuid) : undefined;
      return { e, sceneUuid: r?.f_scene_uuid ?? '', name: s?.legacy_scenario_id || s?.name || e.f_scene_run_uuid.slice(-8), category: s?.category ?? '', mode: r?.mode, latest: latestSeq.get(e.f_scene_run_uuid) === e.run_seq };
    });
  }, [execs.data, runs.data, scenes.data]);

  const categories = useMemo(() => [...new Set(rows.map((r) => r.category).filter(Boolean))].sort(), [rows]);
  const shown = useMemo(() => {
    const since = days ? Date.now() - days * 86400_000 : 0;
    const k = q.trim().toLowerCase();
    return rows.filter((r) => (!cat || r.category === cat) && (!k || r.name.toLowerCase().includes(k)) && (!since || (r.e.started_ms ?? 0) >= since));
  }, [rows, q, cat, days]);

  // 縮圖:每個場景只抓一次場景樹,只抓目前顯示到的
  const [trees, setTrees] = useState<Record<string, SceneTree3d | null>>({});
  useEffect(() => {
    const need = [...new Set(shown.map((r) => r.sceneUuid))].filter((u) => u && !(u in trees)).slice(0, 12);
    if (!need.length) return;
    setTrees((t) => ({ ...t, ...Object.fromEntries(need.map((u) => [u, null])) }));
    need.forEach((u) => getSceneTree3d(u).then((tr) => setTrees((t) => ({ ...t, [u]: tr }))).catch(() => undefined));
  }, [shown, trees]);

  return { rows: shown, total: rows.length, status: execs.status, error: execs.error ?? runs.error, categories, q, setQ, cat, setCat, days, setDays, trees };
}
