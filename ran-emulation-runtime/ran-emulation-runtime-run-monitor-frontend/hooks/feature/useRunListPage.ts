'use client';
import { useMemo, useState } from 'react';
import { POLL_MS } from '@/config';
import { useAsync } from '@/hooks/base/useAsync';
import { usePolling } from '@/hooks/base/usePolling';
import { getDuTick, listRuns, listScenes } from '@/services/api/runs';

export function useRunListPage() {
  const runs = useAsync(listRuns, []); const scenes = useAsync(listScenes, []); const tick = useAsync(getDuTick, []);
  const [onlyActive, setOnlyActive] = useState(false);
  usePolling(runs.refetch, POLL_MS, true); usePolling(tick.refetch, POLL_MS, true);
  const sceneName = useMemo(() => new Map((scenes.data ?? []).map((s) => [s.scene_uuid, s.legacy_scenario_id || s.name])), [scenes.data]);
  const rows = useMemo(() => {
    const all = [...(runs.data ?? [])].sort((a, b) => (b.started_at ?? b.scene_run_uuid).localeCompare(a.started_at ?? a.scene_run_uuid));
    return (onlyActive ? all.filter((r) => r.status === 'running') : all).map((r) => ({ run: r, sceneName: sceneName.get(r.f_scene_uuid) ?? r.f_scene_uuid }));
  }, [runs.data, sceneName, onlyActive]);
  return { rows, status: runs.status, error: runs.error, duTick: tick.data, onlyActive, setOnlyActive, refetch: runs.refetch };
}
