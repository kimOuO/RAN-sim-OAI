'use client';
import { useEffect, useMemo, useState } from 'react';
import { SCENE_CATEGORIES, categoryOf } from '@/config';
import { useAsync } from '@/hooks/base/useAsync';
import { listSceneRuns, precomputeRun, readPrecompute, startRun, stopPrecompute, stopRun, updateSceneRun, type PrecomputeStatus } from '@/services/api/runs';
import { createScene, deleteScene, listScenes } from '@/services/api/scenes';
import type { Scene, SceneRun } from '@/types/registry';

export function useSceneListPage() {
  const scenes = useAsync(listScenes, []);
  const runs = useAsync(() => listSceneRuns(), []);
  const [busy, setBusy] = useState<string | null>(null);
  /** precomputing 中的 run 每 10 s 拉一次進度 */
  const [precomp, setPrecomp] = useState<Record<string, PrecomputeStatus>>({});
  useEffect(() => { const ids = (runs.data ?? []).filter((r) => r.status === 'precomputing').map((r) => r.scene_run_uuid); if (!ids.length) return;
    const tick = () => ids.forEach((id) => readPrecompute(id).then((s) => setPrecomp((p) => ({ ...p, [id]: s }))).catch(() => undefined));
    tick(); const t = setInterval(() => { tick(); runs.refetch(); }, 10_000); return () => clearInterval(t); }, [runs.data]);   // eslint-disable-line react-hooks/exhaustive-deps
  const [filter, setFilter] = useState(''); const [category, setCategory] = useState<string>('all');
  const runsByScene = useMemo(() => { const m = new Map<string, SceneRun[]>(); for (const r of runs.data ?? []) { const a = m.get(r.f_scene_uuid) ?? []; a.push(r); m.set(r.f_scene_uuid, a); } return m; }, [runs.data]);
  const all = useMemo(() => [...(scenes.data ?? [])].sort((a, b) => b.scene_updated_at.localeCompare(a.scene_updated_at)), [scenes.data]);
  const counts = useMemo(() => { const m: Record<string, number> = { all: all.length }; for (const s of all) { const k = categoryOf(s.legacy_scenario_id); m[k] = (m[k] ?? 0) + 1; } return m; }, [all]);
  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return all.filter((s) => (category === 'all' || categoryOf(s.legacy_scenario_id) === category) && (!q || s.name.toLowerCase().includes(q) || s.legacy_scenario_id.toLowerCase().includes(q)))
      .map((s) => ({ scene: s, category: categoryOf(s.legacy_scenario_id), runs: runsByScene.get(s.scene_uuid) ?? [] }));
  }, [all, filter, category, runsByScene]);
  async function withBusy(key: string, fn: () => Promise<unknown>) { setBusy(key); try { await fn(); } finally { setBusy(null); scenes.refetch(); runs.refetch(); } }
  return {
    scenes: visible, status: scenes.status, error: scenes.error, busy, filter, setFilter, category, setCategory, counts,
    categories: [{ key: 'all', label: '全部' }, ...SCENE_CATEGORIES.map((c) => ({ key: c.key, label: c.label })), { key: 'other', label: '其他' }].filter((c) => c.key === 'all' || counts[c.key]),
    create: (name: string) => withBusy('create', () => createScene({ name })),
    remove: (s: Scene) => withBusy(s.scene_uuid, () => deleteScene(s.scene_uuid)),
    start: (r: SceneRun) => withBusy(r.scene_run_uuid, () => startRun(r.scene_run_uuid, r.speed_x, r.sim_dt_ms)),
    stop: (r: SceneRun) => withBusy(r.scene_run_uuid, () => stopRun(r.scene_run_uuid)),
    precompute: (r: SceneRun) => withBusy(r.scene_run_uuid, () => precomputeRun(r.scene_run_uuid)),
    // 場景管理頁直接切模式 / 倍速,不必進編輯器。切到 live 時把倍速壓回 1 ——
    // live 每個 tick 都要即時 ray tracing,實測(18 UE × 3 cell、sim_dt 500 ms)
    // 只到約 1.6× 實時,設高了 RU 跟不上會被健康檢查重啟。
    setMode: (r: SceneRun, mode: SceneRun['mode']) => withBusy(r.scene_run_uuid,
      () => updateSceneRun(r.scene_run_uuid, mode === 'live' ? { mode, speed_x: 1 } : { mode })),
    setSpeed: (r: SceneRun, speed_x: number) => withBusy(r.scene_run_uuid,
      () => updateSceneRun(r.scene_run_uuid, { speed_x })),
    stopPrecompute: (r: SceneRun) => withBusy(r.scene_run_uuid, () => stopPrecompute(r.scene_run_uuid)),
    precomp,
  };
}
