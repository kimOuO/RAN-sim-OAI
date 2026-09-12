'use client';
import { useMemo, useState } from 'react';
import { useAsync } from '@/hooks/base/useAsync';
import { listSceneRuns } from '@/services/api/runs';
import { createScene, deleteScene, listScenes } from '@/services/api/scenes';
import { startRun, stopRun } from '@/services/api/runs';
import type { Scene, SceneRun } from '@/types/registry';

export function useSceneListPage() {
  const scenes = useAsync(listScenes, []);
  const runs = useAsync(() => listSceneRuns(), []);
  const [busy, setBusy] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const runsByScene = useMemo(() => {
    const m = new Map<string, SceneRun[]>();
    for (const r of runs.data ?? []) { const a = m.get(r.f_scene_uuid) ?? []; a.push(r); m.set(r.f_scene_uuid, a); }
    return m;
  }, [runs.data]);
  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const all = [...(scenes.data ?? [])].sort((a, b) => b.scene_updated_at.localeCompare(a.scene_updated_at));
    return q ? all.filter((s) => s.name.toLowerCase().includes(q) || s.legacy_scenario_id.toLowerCase().includes(q)) : all;
  }, [scenes.data, filter]);
  async function withBusy(key: string, fn: () => Promise<unknown>) { setBusy(key); try { await fn(); } finally { setBusy(null); scenes.refetch(); runs.refetch(); } }
  return {
    scenes: visible, status: scenes.status, error: scenes.error, runsByScene, busy, filter, setFilter,
    create: (name: string) => withBusy('create', () => createScene({ name })),
    remove: (s: Scene) => withBusy(s.scene_uuid, () => deleteScene(s.scene_uuid)),
    start: (r: SceneRun) => withBusy(r.scene_run_uuid, () => startRun(r.scene_run_uuid, r.speed_x, r.sim_dt_ms)),
    stop: (r: SceneRun) => withBusy(r.scene_run_uuid, () => stopRun(r.scene_run_uuid)),
    refetch: () => { scenes.refetch(); runs.refetch(); },
  };
}
